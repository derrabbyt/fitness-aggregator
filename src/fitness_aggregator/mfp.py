"""Run Mason's mfp-mcp with its session kept in state/mfp/.

mfp-mcp stores cookies.json under XDG_CONFIG_HOME and the auto-refresh browser
profile plus its SQLite cache under XDG_DATA_HOME. MyFitnessPal rotates the
session cookie on use, so mfp-mcp must be the only thing using the session and
MFP_COOKIE must never be passed to it: with MFP_COOKIE set, mfp-mcp stops saving
the rotated cookie and the session dies within hours. MFP_COOKIE in .env is only
read by scripts/mfp_auth.py to connect a new session.
"""

import os
import shutil
import sys

from .config import STATE, load_env

MFP_STATE = STATE / "mfp"


def mfp_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "MFP_COOKIE"}
    env["XDG_CONFIG_HOME"] = str(MFP_STATE / "config")
    env["XDG_DATA_HOME"] = str(MFP_STATE / "data")
    username = load_env().get("MFP_USERNAME")
    if username:
        # MFP's profile endpoint returns 500 for this account, so mfp-mcp needs it.
        env["MFP_USERNAME"] = username
    return env


def mfp_command() -> str:
    exe = shutil.which("mfp-mcp", path=os.path.dirname(sys.executable))
    if not exe:
        sys.exit("mfp-mcp is not installed in this environment; run `uv sync`.")
    return exe


def serve() -> None:
    os.umask(0o077)
    MFP_STATE.mkdir(parents=True, exist_ok=True)
    exe = mfp_command()
    os.execve(exe, [exe, *sys.argv[1:]], mfp_env())
