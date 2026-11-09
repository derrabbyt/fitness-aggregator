"""The real api client: fa-api over HTTP, the coach's only way to MFP and Hevy.

Sync reads come from the api's REST endpoints (`api_url`, ticket 02); the
MFP goal is set through the `fitness_set_goal` MCP tool (`tools_url`, ticket
06): sent once, read back once, never retried.
"""


class HttpApiClient:
    def __init__(self, api_url: str, tools_url: str):
        self.api_url = api_url.rstrip("/")
        self.tools_url = tools_url.rstrip("/")
