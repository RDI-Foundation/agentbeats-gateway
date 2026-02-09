# AgentBeats Assessment Service

Initiates an assessment by sending participants and assessment configuration to the Green agent via A2A. Parses the Green agent's response and serves results as JSON.

The endpoint at `/` returns JSON with a `status` field set to `running` while the assessment is in progress. Once the Green agent finishes, the endpoint returns `status` set to the final A2A task state (e.g. `completed`, `failed`) and `results` containing the parsed artifact data.

## Configuration

| Source | Name | Description |
|---|---|---|
| Env | `GREEN_URL` | Base URL of the Green agent (required) |
| Env | `PARTICIPANTS` | JSON mapping role to participant URL |
| Env | `ASSESSMENT_CONFIG` | JSON assessment configuration |
| Arg | `--port` | HTTP server port |