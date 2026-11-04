"""Connect Hevy once. Tokens are cached in state/hevy and refresh themselves.

    uv run scripts/hevy_auth.py            # opens hevy.com in a browser to log in
    wl-paste -n | uv run scripts/hevy_auth.py --cookie   # or paste the auth2.0-token cookie
"""

import sys

from fitness_aggregator import hevy

if "--cookie" in sys.argv[1:]:
    hevy.import_cookie(sys.stdin.read())
with hevy.client(allow_browser_login=True) as c:
    print("Connected to Hevy as", c.users.get_account()["username"])
