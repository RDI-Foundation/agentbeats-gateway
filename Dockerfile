FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV PYTHONUNBUFFERED=1

RUN adduser assessment && mkdir -p /output && chown assessment:assessment /output
USER assessment
WORKDIR /home/assessment

COPY pyproject.toml uv.lock ./
COPY src src

RUN uv sync --locked

ENTRYPOINT ["uv", "run", "python", "src/main.py"]
EXPOSE 8080
