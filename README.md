# AgentBeats Gateway

Orchestrator and reverse proxy for AgentBeats assessments in Amber:
- initiates an assessment by sending participants and assessment configuration to the Green agent via A2A
- routes participant URLs through itself
- parses the Green agent's response and serves results as JSON

The gateway now assumes Amber's current A2A routing model. It builds participant URLs from its own
proxy address and rewrites loopback agent-card URLs so follow-up requests continue to flow through
the gateway instead of leaking internal container addresses.

For compatibility with older manifests, the gateway manifest still accepts extra config such as
`callback_urls` and the legacy optional `green_mcp` slot. The current runtime ignores those inputs.

The endpoint at `/` returns JSON with a `status` field set to `running` while the assessment is in progress. Once the session finishes, the endpoint returns `status` set to the final A2A task state (e.g. `completed`, `failed`) and `results` containing the parsed artifact data.

## Configuration

| Source | Name | Description |
|---|---|---|
| Env | `SERVICE_URLS` | JSON object mapping slot names to participant endpoint URLs (required) |
| Env | `PARTICIPANT_ROLES` | JSON object mapping slot names to semantic role names (required) |
| Env | `ASSESSMENT_CONFIG` | Assessment parameters |
| Arg | `--proxy-port` | Proxy server port (default: 8080) |
| Arg | `--results-port` | Results server port (default: 8081) |
