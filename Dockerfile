# fitness-aggregator: one image, three services (see docker-compose.yml).
#   api    FastAPI + Angular UI (:8000) and the MFP/Hevy MCP tools (:8001, internal)
#   bot    food bot: Telegram (Pydantic AI, own venv in bot/) + whisper.cpp for voice notes
#   coach  the coach: Telegram + scheduler (Anthropic SDK, own venv in coach/)
# All versions are pinned; bump them deliberately.

ARG DEBIAN_IMAGE=debian:bookworm-slim
ARG UV_VERSION=0.11.29

# --- whisper.cpp: CPU build for Zen 1 and newer (AVX2/FMA, no -march=native,
# so an image built on one machine runs on the other) plus the small model.
FROM ${DEBIAN_IMAGE} AS whisper
ARG WHISPER_COMMIT=d2a764c648779feb36d44363f212a29b00aad1af
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN git init /src && cd /src \
    && git fetch --depth 1 https://github.com/ggml-org/whisper.cpp "$WHISPER_COMMIT" \
    && git checkout -q FETCH_HEAD \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
        -DWHISPER_SDL2=OFF -DGGML_NATIVE=OFF \
        -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON \
    && cmake --build build -j"$(nproc)" --target whisper-cli \
    && install -m 755 build/bin/whisper-cli /usr/local/bin/whisper-cli
RUN mkdir -p /models && curl -fsSL -o /models/ggml-small.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

# --- Angular frontend
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npx ng build

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- runtime
FROM ${DEBIAN_IMAGE}
ARG UID=1000
ARG GID=1000

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PYTHONUNBUFFERED=1

# git: uv installs the pinned MFP/Hevy connectors from git; ffmpeg: voice
# notes to wav for whisper; curl: healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git ffmpeg tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=whisper /usr/local/bin/whisper-cli /usr/local/bin/whisper-cli
COPY --from=whisper /models/ggml-small.bin /usr/local/share/whisper-cpp/models/ggml-small.bin

# Same uid/gid as the host user, so files on the state/ bind mount match.
# Everything below is installed as that user, so no chown layer copies it.
RUN groupadd -g "$GID" app && useradd -m -u "$UID" -g "$GID" -s /bin/bash app \
    && mkdir -p /app/state /opt/uv-python /opt/ms-playwright \
    && chown app:app /app /app/state /opt/uv-python /opt/ms-playwright

WORKDIR /app
USER app
COPY --chown=app:app pyproject.toml uv.lock .python-version ./
# Chromium headless shell: mfp-mcp renews the MFP session with
# launch_persistent_context(headless=True), which uses it.
RUN uv python install 3.13 \
    && uv sync --no-install-project --no-dev \
    && .venv/bin/playwright install --only-shell chromium
USER root
RUN /app/.venv/bin/playwright install-deps chromium-headless-shell && rm -rf /var/lib/apt/lists/*
USER app
COPY --chown=app:app src/ src/
COPY --chown=app:app scripts/ scripts/
COPY --chown=app:app CLAUDE.md README.md ./
RUN uv sync --no-dev
# The bot has its own environment (bot/.venv): see bot/pyproject.toml. It
# includes pytest, so `docker compose run --rm test` works without uv on the host.
COPY --chown=app:app bot/pyproject.toml bot/uv.lock bot/.python-version bot/
RUN cd bot && uv sync --no-install-project
COPY --chown=app:app bot/src/ bot/src/
RUN cd bot && uv sync
# The coach is its own project too (coach/.venv), with its skills package
# (skills, params, schemas) read at runtime from coach/coach-skills.
COPY --chown=app:app coach/pyproject.toml coach/uv.lock coach/.python-version coach/
RUN cd coach && uv sync --no-install-project
COPY --chown=app:app coach/src/ coach/src/
RUN cd coach && uv sync
COPY --chown=app:app coach/coach-skills/ coach/coach-skills/
COPY --chown=app:app coach/data/ coach/data/
COPY --from=web --chown=app:app /web/dist web/dist

ENV HOME=/home/app PATH=/app/.venv/bin:$PATH
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["fa-api"]
