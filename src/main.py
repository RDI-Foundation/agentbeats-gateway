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
        except Exception:
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


def get_participant_service_urls(config) -> list[str]:
    return [
        config.service_urls[slot]
        for slot in config.participant_roles
        if slot in config.service_urls
    ]


def get_agent_routes(config) -> dict[str, str]:
    return {
        role: config.service_urls[slot]
        for slot, role in config.participant_roles.items()
        if slot in config.service_urls
    }


async def run_assessment_task(config):
    global result_data

    print("Waiting for agents to be ready...")
    ready = await wait_for_agents(get_participant_service_urls(config))
    if not ready:
        result_data = {"status": "failed", "error": "Timeout: agents not ready"}
        return

    print("Starting assessment.")

    green_url = config.service_urls["green"]
    gateway_url = f"http://127.0.0.1:{config.proxy_port}"
    participants = {
        role: f"{gateway_url}/{role}"
        for slot, role in config.participant_roles.items()
        if slot != "green" and slot in config.service_urls
    }

    result = await run_assessment(green_url, participants, config.assessment_config)
    print(f"Assessment finished with status: {result['status']}")
    result_data = result


async def main():
    config = load_config()
    print(f"Config: {config}")

    proxy = Proxy(agent_routes=get_agent_routes(config))

    proxy_server = uvicorn.Server(
        uvicorn.Config(proxy.app, host="0.0.0.0", port=config.proxy_port, log_level="info")
    )
    results_server = uvicorn.Server(
        uvicorn.Config(result_app, host="0.0.0.0", port=config.results_port, log_level="info")
    )

    proxy_task = asyncio.create_task(proxy_server.serve())
    results_task = asyncio.create_task(results_server.serve())
    assessment_task = asyncio.create_task(run_assessment_task(config))

    await asyncio.gather(proxy_task, results_task, assessment_task)


if __name__ == "__main__":
    asyncio.run(main())
