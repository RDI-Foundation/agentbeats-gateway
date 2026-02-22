import re
import json
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route


_LOCALHOST_RE = re.compile(r'https?://(?:localhost|127\.0\.0\.1)(:\d+)?')


def _rewrite_agent_card(body: bytes, route: str, green_callback_url: str) -> bytes:
    """Rewrite the agent card's url field to point back through the gateway (green's perspective)."""
    try:
        card = json.loads(body)
    except json.JSONDecodeError:
        return body
    if "url" in card:
        card["url"] = f"{green_callback_url}/{route}"
    return json.dumps(card).encode()


def _rewrite_localhost_urls(body: bytes, target_callback_url: str) -> bytes:
    """Replace localhost URL bases in the request body with the target's callback URL."""
    return _LOCALHOST_RE.sub(target_callback_url.rstrip("/"), body.decode()).encode()


class Proxy:
    def __init__(
        self,
        agent_routes: dict[str, str],   # route key -> upstream URL
        callback_urls: dict[str, str],  # slot -> callback URL (includes "green")
        role_to_slot: dict[str, str],   # role name -> slot name
    ):
        self.agent_routes = agent_routes
        self.callback_urls = callback_urls
        self.role_to_slot = role_to_slot

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

        slot = self.role_to_slot.get(name, name)
        base_callback = self.callback_urls.get(slot)
        if not base_callback:
            if body:
                print(f"Warning: no callback URL for {slot}, skipping localhost URL rewrite")
        else:
            body = _rewrite_localhost_urls(body, f"{base_callback}/green_mcp")

        req = self.client.build_request(
            method=request.method,
            url=target_url,
            headers=request.headers.raw,
            content=body,
        )

        try:
            if path == ".well-known/agent-card.json":
                resp = await self.client.send(req)
                green_callback = self.callback_urls.get("green", "")
                response_body = _rewrite_agent_card(resp.content, name, green_callback)
                headers = {k: v for k, v in resp.headers.items() if k.lower() != "content-length"}
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
                headers=dict(resp.headers),
            )
        except httpx.ConnectError:
            return Response(f"Failed to connect to upstream: {name}", status_code=502)
        except httpx.TimeoutException:
            return Response(f"Upstream timeout: {name}", status_code=504)
