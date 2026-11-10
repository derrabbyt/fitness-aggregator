"""The context mfp-mcp's `with_session` and tools report progress to, for
calls made in-process (api.py, mfp_goal.py) rather than over MCP."""

import logging

logger = logging.getLogger("fitness_aggregator.api")


class LogContext:
    """Stands in for the MCP request context that mfp-mcp reports progress to."""

    async def info(self, message: str) -> None:
        logger.info(message)
