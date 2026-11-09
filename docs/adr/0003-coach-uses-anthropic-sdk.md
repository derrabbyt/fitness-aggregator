# The coach calls Claude through the Anthropic SDK, not Pydantic AI

The food bot uses Pydantic AI, but the coach uses the Anthropic Python SDK directly, for explicit control over prompt caching (core and phase skills as a stable cached prefix), JSON-schema output for the weekly verdict, and tool use. The endpoint stays user-configurable (`COACH_ANTHROPIC_BASE_URL` / `COACH_ANTHROPIC_API_KEY` / `COACH_MODEL`, falling back to the shared `ANTHROPIC_*` values), so any Anthropic-compatible proxy works; the cost is that OpenAI-style endpoints are not supported without switching libraries.
