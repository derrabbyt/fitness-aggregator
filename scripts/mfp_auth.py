"""Connect MyFitnessPal once (or --check). With the api stopped, see README:

    docker compose run --rm --no-deps -v ./.env:/app/.env:ro api python scripts/mfp_auth.py

Reads MFP_COOKIE from .env, validates it with `mfp-mcp auth`, saves it to
state/mfp and seeds the headless browser profile that renews the session from
then on. Get the cookie from a private-window login and close that window
without logging out. The cookie goes over stdin and is never printed.
"""

import subprocess
import sys

from fitness_aggregator.config import load_env
from fitness_aggregator.mfp import MFP_STATE, mfp_command, mfp_env

MFP_STATE.mkdir(parents=True, exist_ok=True)
cmd = [mfp_command(), "auth"]
if "--check" in sys.argv[1:]:
    sys.exit(subprocess.run([*cmd, "--check"], env=mfp_env()).returncode)

cookie = load_env().get("MFP_COOKIE", "").strip()
if not cookie:
    sys.exit("Put MFP_COOKIE=<__Secure-next-auth.session-token value> in .env first.")
result = subprocess.run(cmd, input=cookie + "\n", text=True, env=mfp_env(), capture_output=True)
print(result.stdout.replace(cookie, "<cookie>"))
print(result.stderr.replace(cookie, "<cookie>"), file=sys.stderr)
sys.exit(result.returncode)
