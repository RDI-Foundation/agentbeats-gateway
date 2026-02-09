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
    ready = await wait_for_agents([config.green_url])
    if not ready:
        print("Error: Green agent not ready.")
        result_data = {"status": "failed", "error": "Timeout: green agent not ready"}
        return

    # extra time for participants to become ready in Amber scenarios
    # can be removed after healthchecks are added to Amber (or if we bind and wait for participants)
    await asyncio.sleep(10)
    print("Starting assessment.")

    result = await run_assessment(
        config.green_url, config.participants, config.assessment_config
    )
    print(f"Assessment finished with status: {result['status']}")
    result_data = result


async def main():
    config = load_config()
    server = uvicorn.Server(
        uvicorn.Config(result_app, host="0.0.0.0", port=config.port, log_level="info")
    )
    server_task = asyncio.create_task(server.serve())
    _assessment_task = asyncio.create_task(run_assessment_task(config))
    await server_task


if __name__ == "__main__":
    asyncio.run(main())