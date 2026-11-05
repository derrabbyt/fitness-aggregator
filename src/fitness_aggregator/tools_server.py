"""MFP and Hevy MCP tools over streamable HTTP, served by the api process.

    http://<host>:8001/mfp/mcp    Mason's mfp-mcp tools (all of them)
    http://<host>:8001/hevy/mcp   read-only Hevy tools

Runs in the same process as the FastAPI app, so one process owns the MFP
session (state/mfp). Not published outside the Docker network: anything that
can reach this port can write to the diary.
"""

import contextlib

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

# Host headers the bot (api:8001 inside compose) and local runs send.
ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "api:*"]


def build_app() -> Starlette:
    from myfitnesspal_mcp import server as mfp_server  # after api.py set the MFP env

    from .api import fitness_get_activity, fitness_quick_add
    from .hevy_mcp import mcp as hevy_mcp

    # Steps/synced workouts and Quick Add aren't among mfp-mcp's tools.
    mfp_server.mcp.tool(title="Get activity (steps, exercise)", annotations=mfp_server.READS_MFP)(fitness_get_activity)
    mfp_server.mcp.tool(title="Quick add calories", annotations=mfp_server.ADDS_TO_MFP)(fitness_quick_add)
    servers = {"mfp": mfp_server.mcp, "hevy": hevy_mcp}
    for server in servers.values():
        # Stateless: the bot reconnects cleanly after either side restarts.
        server.settings.stateless_http = True
        server.settings.json_response = True
        server.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=ALLOWED_HOSTS, allowed_origins=[]
        )
    apps = {name: server.streamable_http_app() for name, server in servers.items()}

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with contextlib.AsyncExitStack() as stack:
            for server in servers.values():
                await stack.enter_async_context(server.session_manager.run())
            yield

    return Starlette(routes=[Mount(f"/{name}", app=app) for name, app in apps.items()], lifespan=lifespan)
