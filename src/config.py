import argparse
import json
import os
from dataclasses import dataclass


@dataclass
class Config:
    proxy_port: int
    results_port: int
    service_urls: dict[str, str]        # slot name -> participant URL
    participant_roles: dict[str, str]   # slot name -> agent role name
    callback_urls: dict[str, str]       # slot name -> gateway URL (reverse bindings)
    assessment_config: dict


def load_config() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-port", type=int, default=8080)
    parser.add_argument("--results-port", type=int, default=8081)
    args = parser.parse_args()

    service_urls_raw = os.environ.get("SERVICE_URLS")
    if not service_urls_raw:
        raise ValueError("SERVICE_URLS is required")
    service_urls = {
        slot: data["url"] if isinstance(data, dict) else data
        for slot, data in json.loads(service_urls_raw).items()
    }

    participant_roles_raw = os.environ.get("PARTICIPANT_ROLES")
    if not participant_roles_raw:
        raise ValueError("PARTICIPANT_ROLES is required")
    participant_roles = json.loads(participant_roles_raw)

    callback_urls_raw = os.environ.get("CALLBACK_URLS")
    if not callback_urls_raw:
        raise ValueError("CALLBACK_URLS is required")
    callback_urls = json.loads(callback_urls_raw)

    assessment_config_raw = os.environ.get("ASSESSMENT_CONFIG", "{}")
    assessment_config = json.loads(assessment_config_raw)

    return Config(
        proxy_port=args.proxy_port,
        results_port=args.results_port,
        service_urls=service_urls,
        participant_roles=participant_roles,
        callback_urls=callback_urls,
        assessment_config=assessment_config,
    )
