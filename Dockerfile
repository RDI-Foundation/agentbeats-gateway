FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV PYTHONUNBUFFERED=1

RUN adduser gateway
USER gateway
WORKDIR /home/gateway

COPY pyproject.toml uv.lock ./
COPY src src

RUN uv sync --locked

ENTRYPOINT ["uv", "run", "python", "src/main.py"]
EXPOSE 8080
EXPOSE 8081
