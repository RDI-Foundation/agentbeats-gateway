import asyncio
import time
import uvicorn
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.client import A2ACardResolver

from assessment import run_assessment
from config import load_config
from proxy import Proxy


async def wait_for_agents(endpoints: list[str], timeout: int = 30) -> bool:
    print(f"Waiting for {len(endpoints)} agent(s) to be ready...")
    start_time = time.time()

    async def check_endpoint(endpoint: str) -> bool:
        """Check if an endpoint is responding by fetching the agent card."""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=endpoint)
                await resolver.get_agent_card()
                return True
        except Exception as e:
            # Any exception means the agent is not ready
            return False

    while time.time() - start_time < timeout:
        ready_count = 0
        for endpoint in endpoints:
            if await check_endpoint(endpoint):
                ready_count += 1

        if ready_count == len(endpoints):
            return True

        print(f"  {ready_count}/{len(endpoints)} agents ready, waiting...")
        await asyncio.sleep(1)

    print(
        f"Timeout: Only {ready_count}/{len(endpoints)} agents became ready after {timeout}s"
    )
    return False


result_data = {"status": "running"}


async def get_result(request):
    return JSONResponse(result_data)


result_app = Starlette(routes=[Route("/", get_result)])


async def run_assessment_task(config):
    global result_data

    print("Waiting for agents to be ready...")
    a2a_urls = [url for key, url in config.service_urls.items() if not key.endswith(("_http", "_mcp"))]
    ready = await wait_for_agents(a2a_urls)
    if not ready:
        result_data = {"status": "failed", "error": "Timeout: agents not ready"}
        return

    print("Starting assessment.")

    green_url = config.service_urls["green"]
    gateway_url = config.callback_urls["green"]
    participants = {
        role: f"{gateway_url}/{role}"
        for slot, role in config.participant_roles.items()
        if slot != "green"
    }

    result = await run_assessment(green_url, participants, config.assessment_config)
    print(f"Assessment finished with status: {result['status']}")
    result_data = result


async def main():
    config = load_config()
    print(f"Config: {config}")

    agent_routes = {
        role: config.service_urls[slot]
        for slot, role in config.participant_roles.items()
        if slot in config.service_urls
    }
    for slot, url in config.service_urls.items():
        if slot.endswith(("_http", "_mcp")):
            agent_routes[slot] = url

    role_to_slot = {role: slot for slot, role in config.participant_roles.items()}

    proxy = Proxy(
        agent_routes=agent_routes,
        callback_urls=config.callback_urls,
        role_to_slot=role_to_slot,
    )

    proxy_server = uvicorn.Server(
        uvicorn.Config(proxy.app, host="0.0.0.0", port=config.proxy_port, log_level="info")
    )
    results_server = uvicorn.Server(
        uvicorn.Config(result_app, host="0.0.0.0", port=config.results_port, log_level="info")
    )

    proxy_task = asyncio.create_task(proxy_server.serve())
    results_task = asyncio.create_task(results_server.serve())
    _assessment_task = asyncio.create_task(run_assessment_task(config))

    await asyncio.gather(proxy_task, results_task)


if __name__ == "__main__":
    asyncio.run(main())