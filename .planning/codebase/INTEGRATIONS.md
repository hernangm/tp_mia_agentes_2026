# External Integrations

**Analysis Date:** 2026-06-17

## LLM Providers

The framework supports two interchangeable LLM providers, selected at runtime by env var. Both are wrapped under the `LLMClient` facade in `mia_agents/llm_client.py`.

**AWS Bedrock (via Converse API):**
- Purpose: Production LLM calls to Amazon Nova family models
- SDK/Client: `boto3` — `boto3.client("bedrock-runtime", region_name=...)`
- Implementation: `BedrockProvider` class in `mia_agents/llm_client.py`
- API: AWS Bedrock Converse API (`client.converse(...)`)
- Supported models:
  - `amazon.nova-micro-v1:0` — 128K context, weak baseline
  - `amazon.nova-lite-v1:0` — 300K context, recommended default
  - `amazon.nova-pro-v1:0` — 300K context, strongest option
- Auth: Standard boto3 credential chain (env vars, profiles, SSO, STS roles)
- Note: `response_format` parameter is accepted but not implemented by this provider; structured output uses the `final_result` tool pattern instead (M2)

**Ollama (local or remote server):**
- Purpose: Local LLM inference without API keys
- SDK/Client: `ollama` Python SDK — `ollama.Client(host=...)`
- Implementation: `OllamaProvider` class in `mia_agents/llm_client.py`
- Recommended models with tool-use support: `llama3.1`, `qwen2.5`
- `response_format` is supported — passed as `format` parameter to Ollama
- Default `num_ctx` overridden to 16384 (Ollama default of 2048 is insufficient for M3 scenarios)

**Custom providers:**
- Students may implement their own provider satisfying `mia_agents.protocols.LLMClient` (single `chat()` method returning `LLMResponse`)
- Injected via `build_agent({"llm_client": custom_client})`
- `MockLLMClient` in `mia_agents/testing/mock_llm.py` is the canonical example

## Environment Variables

**Required for Bedrock:**
| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MODEL_ID` | (none — required) | Full model ID, e.g. `amazon.nova-lite-v1:0` |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | (from boto3 chain) | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | (from boto3 chain) | AWS secret key |
| `AWS_SESSION_TOKEN` | (optional) | For STS/SSO temporary credentials |
| `AWS_PROFILE` | (optional) | Named AWS CLI profile |

**Required for Ollama:**
| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL; presence of this var activates OllamaProvider |
| `OLLAMA_MODEL` | `llama3.1` | Model name to use |

**Provider selection logic** (in `LLMClient.from_env()`, `mia_agents/llm_client.py`):
1. If `OLLAMA_HOST` is set → use `OllamaProvider`
2. Else if `BEDROCK_MODEL_ID` is set → use `BedrockProvider`
3. Else → raise `RuntimeError`

**Other:**
| Variable | Description |
|----------|-------------|
| `MIA_ENV_FILE` | Override path for the `.env` file loaded by `mia_agents/_env.py` |

## Environment File Loading

- Custom `.env` loader: `mia_agents/_env.py` — `load_env_files()`
- No third-party dotenv library used
- Discovery order: `MIA_ENV_FILE` → cwd and 4 parents → scaffold root
- Does NOT override variables already set in the environment
- Skips `op://...` values (1Password references that must be resolved by `op run`)
- `.env` file should NOT be committed to the repository

## Data Storage

**Databases:** None  
**File Storage:** Local filesystem only (file-reader tool reads local text files)  
**Caching:** None

## Authentication & Identity

**No user authentication layer.** The system is a course framework; auth is handled entirely at the LLM provider level (AWS IAM / Ollama network access).

## Monitoring & Observability

**Error Tracking:** None configured  
**Logs:** `print()` statements in scripts and CLI; no structured logging framework  
**Token tracking:** `AgentResult.input_tokens` / `AgentResult.output_tokens` accumulate tokens from `LLMResponse` fields reported by each provider

## CI/CD & Deployment

**Hosting:** Not applicable (course submission)  
**CI Pipeline:** Not configured (no `.github/`, `Makefile`, or CI config detected)  
**Grading:** Instructors re-run conformance tests (`tests/conformance/`) against submitted `student_framework/`

## Webhooks & Callbacks

**Incoming:** None  
**Outgoing:** None — all LLM calls are synchronous request/response

---

*Integration audit: 2026-06-17*
