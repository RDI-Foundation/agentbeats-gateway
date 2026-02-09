import json
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import (
    A2ACardResolver,
    ClientConfig,
    ClientFactory,
)
from a2a.types import (
    Artifact,
    DataPart,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TextPart,
)


DEFAULT_TIMEOUT = 300


def print_parts(parts, task_state: str | None = None):
    text_parts, data_parts = parse_parts(parts)

    output = []
    if task_state:
        output.append(f"[Status: {task_state}]")
    if text_parts:
        output.append("\n".join(text_parts))
    if data_parts:
        output.extend(json.dumps(item, indent=2) for item in data_parts)

    print("\n".join(output) + "\n")


async def send_message(
    message: str, base_url: str
) -> tuple[str | None, list[Artifact] | None]:
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=True,
        )
        factory = ClientFactory(config)
        agent_card.url = base_url
        client = factory.create(agent_card)
        outbound_msg = Message(
            kind="message",
            role=Role.user,
            parts=[Part(root=TextPart(kind="text", text=message))],
            message_id=uuid4().hex,
            context_id=None,
        )

        artifacts: list[Artifact] | None = None
        final_status: str | None = None

        async for event in client.send_message(outbound_msg):
            match event:
                case Message() as msg:
                    print_parts(msg.parts)

                case (task, TaskStatusUpdateEvent() as status_event):
                    status = status_event.status
                    parts = status.message.parts if status.message else []
                    print_parts(parts, status.state.value)
                    final_status = status.state.value
                    if status.state.value == "completed":
                        print(task.artifacts)
                        artifacts = task.artifacts

                case (task, TaskArtifactUpdateEvent() as artifact_event):
                    print_parts(artifact_event.artifact.parts, "Artifact update")

                case task, None:
                    status = task.status
                    parts = status.message.parts if status.message else []
                    print_parts(parts, task.status.state.value)
                    final_status = status.state.value
                    if status.state.value == "completed":
                        print(task.artifacts)
                        artifacts = task.artifacts

                case _:
                    print("Unhandled event")

        return final_status, artifacts


def parse_parts(parts) -> tuple[list, list]:
    text_parts = []
    data_parts = []

    for part in parts:
        if isinstance(part.root, TextPart):
            try:
                data_item = json.loads(part.root.text)
                data_parts.append(data_item)
            except Exception:
                text_parts.append(part.root.text.strip())
        elif isinstance(part.root, DataPart):
            data_parts.append(part.root.data)

    return text_parts, data_parts


async def run_assessment(
    green_url: str, participants: dict[str, str], assessment_config: dict[str, Any]
):
    assessment_request = {"participants": participants, "config": assessment_config}
    msg = json.dumps(assessment_request)

    status = None
    artifacts = []
    try:
        status, artifacts = await send_message(msg, green_url)
    except Exception as e:
        print(f"Assessment failed: {e}")
        status = "failed"
    finally:
        all_data_parts = []
        for artifact in artifacts or []:
            _, data_parts = parse_parts(artifact.parts)
            all_data_parts.extend(data_parts)

        output_data = {"status": status, "results": all_data_parts}

        return output_data
