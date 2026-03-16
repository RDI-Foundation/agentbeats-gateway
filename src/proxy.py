import json
from contextlib import asynccontextmanager
from urllib.parse import urlparse, urlunparse

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route


def _rewrite_local_url(url: str, route: str, gateway_base_url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
    }:
        return None

    gateway_base = gateway_base_url.rstrip("/")
    rewritten_path = f"/{route}{parsed.path}" if parsed.path else f"/{route}"
    rewritten = urlparse(f"{gateway_base}{rewritten_path}")
    return urlunparse(
        (
            rewritten.scheme,
            rewritten.netloc,
            rewritten.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _rewrite_agent_card(body: bytes, route: str, gateway_base_url: str) -> bytes:
    """Rewrite loopback agent-card URLs so follow-up calls come back through the gateway."""
    try:
        card = json.loads(body)
    except json.JSONDecodeError:
        return body

    rewritten = False

    if isinstance(card.get("supportedInterfaces"), list):
        for interface in card["supportedInterfaces"]:
            if not isinstance(interface, dict):
                continue
            raw_url = interface.get("url")
            if not isinstance(raw_url, str):
                continue
            updated_url = _rewrite_local_url(raw_url, route, gateway_base_url)
            if updated_url and updated_url != raw_url:
                interface["url"] = updated_url
                rewritten = True

    raw_url = card.get("url")
    if isinstance(raw_url, str):
        updated_url = _rewrite_local_url(raw_url, route, gateway_base_url)
        if updated_url and updated_url != raw_url:
            card["url"] = updated_url
            rewritten = True

    if not rewritten:
        return body

    card.pop("signatures", None)
    return json.dumps(card).encode()


class Proxy:
    def __init__(self, agent_routes: dict[str, str]):  # route key -> upstream URL
        self.agent_routes = agent_routes

        @asynccontextmanager
        async def lifespan(app):
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
            yield
            await self.client.aclose()

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        self.app = Starlette(
            lifespan=lifespan,
            routes=[
                Route("/{name}/{path:path}", self.handle_request, methods=methods),
                Route("/{name}", self.handle_request, methods=methods),
            ],
        )

    async def handle_request(self, request: Request) -> Response:
        name = request.path_params["name"]
        path = request.path_params.get("path", "")

        if name not in self.agent_routes:
            return Response(f"Unknown route: {name}", status_code=404)

        upstream_url = self.agent_routes[name]
        target_url = f"{upstream_url}/{path}" if path else upstream_url
        if request.query_params:
            target_url = f"{target_url}?{request.query_params}"

        print(f"PROXY {name}/{path} -> {target_url}")

        body = await request.body()

        req = self.client.build_request(
            method=request.method,
            url=target_url,
            headers=request.headers.raw,
            content=body,
        )

        try:
            if path == ".well-known/agent-card.json":
                resp = await self.client.send(req)
                gateway_base_url = str(request.base_url).rstrip("/")
                response_body = _rewrite_agent_card(
                    resp.content,
                    name,
                    gateway_base_url,
                )
                headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in {"content-length", "content-encoding"}
                }
                return Response(
                    content=response_body,
                    status_code=resp.status_code,
                    headers=headers,
                )

            resp = await self.client.send(req, stream=True)

            async def stream_body():
                async for chunk in resp.aiter_bytes():
                    yield chunk
                await resp.aclose()

            return StreamingResponse(
                content=stream_body(),
                status_code=resp.status_code,
                headers={
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in {"content-length", "content-encoding"}
                },
            )
        except httpx.ConnectError:
            return Response(f"Failed to connect to upstream: {name}", status_code=502)
        except httpx.TimeoutException:
            return Response(f"Upstream timeout: {name}", status_code=504)
