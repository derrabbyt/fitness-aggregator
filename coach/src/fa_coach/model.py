"""The real model client (Anthropic SDK, ADR 0003), built in ticket 03.

Until then the coach makes no model calls; this placeholder fails loudly if
something tries.
"""

from .config import Settings
from .ports import ModelClient, ModelReply, ModelRequest


class NoModel:
    async def run(self, request: ModelRequest) -> ModelReply:
        raise RuntimeError("the coach has no model client yet")


def build_model_client(settings: Settings) -> ModelClient:
    return NoModel()
