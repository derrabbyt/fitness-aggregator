"""Errors as the user and the database see them: a fixed short message and
the exception's class, never its text (it could quote a request, a header or
a cookie). The full exception goes to the log only."""


def brief(what: str, exc: BaseException) -> str:
    """E.g. "the api call failed (RuntimeError)"."""
    return f"{what} ({type(exc).__name__})"
