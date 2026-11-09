"""Connect Hevy once. Tokens are cached in state/hevy and refresh themselves.

    docker compose run --rm --no-deps -T api python scripts/hevy_auth.py --cookie < cookie.txt
    uv run scripts/hevy_auth.py   # browser login, only on a machine with a display
"""

import sys

from fitness_aggregator import hevy

if "--cookie" in sys.argv[1:]:
    hevy.import_cookie(sys.stdin.read())
with hevy.client(allow_browser_login=True) as c:
    print("Connected to Hevy as", c.users.get_account()["username"])
