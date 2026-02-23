# AgentBeats Gateway

Orchestrator and reverse proxy for AgentBeats assessments in Amber:
- initiates an assessment by sending participants and assessment configuration to the Green agent via A2A
- rewrites participant URLs to route through itself
- parses the Green agent's response and serves results as JSON

The endpoint at `/` returns JSON with a `status` field set to `running` while the assessment is in progress. Once the session finishes, the endpoint returns `status` set to the final A2A task state (e.g. `completed`, `failed`) and `results` containing the parsed artifact data.

## Configuration

| Source | Name | Description |
|---|---|---|
| Env | `SERVICE_URLS` | JSON object mapping slot names to participant endpoint URLs (required) |
| Env | `PARTICIPANT_ROLES` | JSON object mapping slot names to semantic role names (required) |
| Env | `CALLBACK_URLS` | JSON object mapping slot names to the URL each participant uses to reach the gateway (required) |
| Env | `ASSESSMENT_CONFIG` | Assessment parameters |
| Arg | `--proxy-port` | Proxy server port (default: 8080) |
| Arg | `--results-port` | Results server port (default: 8081) |