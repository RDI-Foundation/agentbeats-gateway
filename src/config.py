import argparse
import json
import os
from dataclasses import dataclass


@dataclass
class Config:
    port: int
    green_url: str
    participants: dict[str, str]  # role -> url
    assessment_config: dict


def load_config() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    green_url = os.environ.get("GREEN_URL")
    if not green_url:
        raise ValueError("GREEN_URL is required")

    participant_urls_raw = os.environ.get("PARTICIPANTS", "{}")
    participants = json.loads(participant_urls_raw)

    assessment_config_raw = os.environ.get("ASSESSMENT_CONFIG", "{}")
    assessment_config = json.loads(assessment_config_raw)

    return Config(
        port=args.port,
        green_url=green_url,
        participants=participants,
        assessment_config=assessment_config,
    )