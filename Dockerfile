FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=120

RUN adduser --disabled-password --gecos "" gateway
USER gateway
WORKDIR /home/gateway

COPY --chown=gateway:gateway pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project

COPY --chown=gateway:gateway src src
RUN uv sync --locked

ENTRYPOINT ["uv", "run", "python", "src/main.py"]
EXPOSE 8080
EXPOSE 8081
