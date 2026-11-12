"""Thin HTTP adapter for the web page (ADR 0001): the coach's read models and
edits under `/api/coach/`, served inside the coach process next to Telegram
polling. Not published on the host: `fa-api` passes `/api/coach/` through
unchanged over the compose network. No login: access control is the tailnet.

    GET  /api/coach/<view>?day=...          coach.view (e.g. home, home/food)
    POST /api/coach/refresh/<view>?day=...  coach.refresh: sync, then the view
    POST /api/coach/<command>  {json}       coach.command (a registered web command)
    GET  /api/coach/photos/<date>/<n>       coach.photo: one stored progress photo (JPEG), read-only

Photos are private: no caching by shared caches, and neither their bytes nor
their paths are logged (no access log; a failure logs only the exception).

Errors are `{"error": "<plain reason>"}` with the status of `views.WebError`
(500 for anything unexpected). Refresh and commands run like a Telegram
update: one core call at a time, and whatever they say is sent to Telegram.

Reads (`get_view`, `photo`) run outside the adapter lock on purpose, so the
page never waits behind a sync or a model call. That is safe because they
only read: each SQLite query sees a consistent snapshot. A view built while
a sync is writing may show partly synced data (one query before the sync's
write, the next after); the next load or a refresh shows it whole.
"""

import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .core import Coach
from .views import WebError

logger = logging.getLogger("fa-coach")

# Runs one core call the way the Telegram adapter does (its lock, then the outbox).
Runner = Callable[[Callable[[], Awaitable[Any]]], Awaitable[Any]]


def build_app(coach: Coach, run: Runner) -> Starlette:
    async def get_view(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        return await _respond(lambda: _now(coach.view(name, dict(request.query_params))))

    async def refresh(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        query = dict(request.query_params)
        return await _respond(lambda: run(lambda: coach.refresh(name, query)))

    async def command(request: Request) -> JSONResponse:
        name = request.path_params["name"]
        try:
            body = await request.json() if await request.body() else {}
        except ValueError:
            return JSONResponse({"error": "The body isn't JSON."}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "The body must be a JSON object."}, status_code=400)
        return await _respond(lambda: run(lambda: coach.command(name, body)))

    async def photo(request: Request) -> Response:
        day, number = request.path_params["day"], request.path_params["number"]
        try:
            data = coach.photo(day, number)
        except WebError as exc:
            return JSONResponse({"error": exc.message}, status_code=exc.status)
        except Exception as exc:  # noqa: BLE001 - only the type: a traceback could carry the photo's path
            logger.error("photo request failed (%s)", type(exc).__name__)
            return JSONResponse({"error": "That photo can't be read right now."}, status_code=500)
        return Response(data, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})

    return Starlette(routes=[
        Route("/api/coach/photos/{day}/{number:int}", photo, methods=["GET"]),
        Route("/api/coach/refresh/{name:path}", refresh, methods=["POST"]),
        Route("/api/coach/{name:path}", get_view, methods=["GET"]),
        Route("/api/coach/{name:path}", command, methods=["POST"]),
    ])


async def _now(value: Any) -> Any:
    return value


async def _respond(call: Callable[[], Awaitable[Any]]) -> JSONResponse:
    try:
        return JSONResponse(await call())
    except WebError as exc:
        return JSONResponse({"error": exc.message}, status_code=exc.status)
    except Exception as exc:  # noqa: BLE001
        logger.exception("web request failed")
        return JSONResponse({"error": f"That failed ({type(exc).__name__}). Details are in the coach's log."},
                            status_code=500)


class _Server(uvicorn.Server):
    """Leaves signals to the Telegram application, which owns the process."""

    def capture_signals(self):  # type: ignore[override]
        return contextlib.nullcontext()


async def serve(coach: Coach, run: Runner, host: str, port: int) -> None:
    config = uvicorn.Config(build_app(coach, run), host=host, port=port, log_level="warning", access_log=False)
    logger.info("fa-coach web API on %s:%s", host, port)
    await _Server(config).serve()
