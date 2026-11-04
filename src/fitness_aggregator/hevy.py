"""Hevy client with tokens cached in state/hevy/credentials.json (auto-refreshed)."""

import os
import sys

from hevy_unofficial import (
    CredentialStore,
    HevyBrowserError,
    HevyClient,
    login_via_browser,
    parse_auth20_cookie_value,
)

from .config import STATE

CREDENTIALS = STATE / "hevy" / "credentials.json"
CACHE_KEY = "me"  # only labels the cache entry; Hevy never sees it
PAGE_SIZE = 5  # Hevy answers 400 to the library's default page size of 10


def store() -> CredentialStore:
    os.umask(0o077)  # CredentialStore only restricts the file after writing it
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    return CredentialStore(path=CREDENTIALS)


def import_cookie(raw: str) -> None:
    """Cache tokens from a pasted auth2.0-token cookie value."""
    value = raw.strip().removeprefix("auth2.0-token=")
    try:
        store().save(CACHE_KEY, parse_auth20_cookie_value(value))
    except HevyBrowserError as exc:
        sys.exit(f"That isn't a valid auth2.0-token cookie: {exc}")


def client(*, allow_browser_login: bool = False) -> HevyClient:
    creds = store()
    cached = creds.get(CACHE_KEY)
    if cached:
        tokens = cached.tokens
    elif allow_browser_login:
        tokens, _ = login_via_browser(email=CACHE_KEY, store=creds)
    else:
        raise RuntimeError("Hevy is not connected. Run scripts/hevy_auth.py.")
    return HevyClient(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user_id=tokens.user_id,
        credential_email=CACHE_KEY,
        credential_store=creds,
    )
