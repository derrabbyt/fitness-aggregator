"""`fa-coach`: wires the Coach core to its real dependencies and Telegram.

Environment (see .env.example): COACH_TELEGRAM_BOT_TOKEN,
TELEGRAM_ALLOWED_USER_ID, FA_API_URL, FA_TOOLS_URL, COACH_MODEL,
COACH_DECISION_MODEL, COACH_ANTHROPIC_* (else ANTHROPIC_*).
"""

import logging

from . import telegram_adapter
from .api_client import HttpApiClient
from .clock import SystemClock
from .config import Settings
from .core import Coach
from .model import build_model_client


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token URL
    settings = Settings.from_env()
    outbox = telegram_adapter.QueueOutbox()
    coach = Coach(
        settings.db_path,
        api=HttpApiClient(settings.api_url, settings.tools_url),
        model=build_model_client(settings),
        clock=SystemClock(),
        outbox=outbox,
    )
    telegram_adapter.run(coach, outbox, settings.telegram_token, settings.allowed_user_id)


if __name__ == "__main__":
    main()
