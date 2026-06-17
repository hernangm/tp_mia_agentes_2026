# Technology Stack

**Analysis Date:** 2026-06-17

## Languages

**Primary:**
- Python 3.10+ — All source code; minimum version enforced by `X | Y` union syntax and `match` expressions used throughout

## Runtime

**Environment:**
- CPython 3.10 or higher (3.11.x recommended per README)

**Package Manager:**
- pip with virtualenv (`python -m venv .venv`)
- Lockfile: Not present (only `requirements.txt` with `>=` pins)

## Frameworks & Libraries

**Core runtime dependencies** (from `requirements.txt`):

| Package | Version pin | Role |
|---------|-------------|------|
| `ollama` | `>=0.4.0` | SDK for local Ollama LLM server |
| `boto3` | `>=1.34.0` | AWS SDK — used exclusively for Bedrock Converse API |
| `pydantic` | `>=2.0.0` | Data validation, JSON Schema generation from callables, `BaseModel` for structured output |
| `pytest` | `>=8.0.0` | Test runner for all conformance and unit tests |

**Standard library modules used heavily:**
- `dataclasses` — `ToolCall`, `LLMResponse`, `ToolSchema`, `AgentStep`, `AgentResult` in `mia_agents/types.py`
- `inspect`, `typing` — introspection for `ToolSchema.from_callable` in `mia_agents/tool_schema.py`
- `json`, `uuid`, `os`, `abc` — used in `mia_agents/llm_client.py`
- `pathlib`, `argparse` — used in `mia_agents/_env.py` and `scripts/`

## Key Dependencies

**Infrastructure:**
- `pydantic` — drives the entire tool schema generation system; `ToolSchema.from_callable` uses `create_model`, `Field`, `get_type_hints`, and `model_json_schema()`
- `boto3` — wraps AWS Bedrock Converse API in `BedrockProvider`; reads credentials from the standard boto3 chain (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)
- `ollama` — wraps a running Ollama server in `OllamaProvider`; uses `ollama.Client`

## Tooling

**Test runner:**
```bash
pytest tests/conformance/test_m1.py       # Milestone 1
pytest tests/conformance/test_m2.py       # Milestone 2
pytest tests/conformance/test_m3_world.py # Milestone 3 (world)
pytest tests/test_ollama_provider.py      # Ollama provider (mocked)
pytest tests/test_bedrock_provider.py     # Bedrock provider (mocked)
pytest tests/test_tool_schema.py          # Tool schema unit tests
```

**CLI entry points:**
```bash
python -m mia_agents.cli run --module student_framework --message "..."
python -m mia_world.cli list
python -m mia_world.cli run --scenario easy
python scripts/bedrock_llm_smoke.py       # Bedrock smoke test
```

**Environment configuration:**
- `mia_agents/_env.py` — custom `.env` loader (no third-party dotenv library); auto-discovers `.env` up to 4 directories above cwd and respects `MIA_ENV_FILE` override
- No `pyproject.toml`, `setup.py`, or `setup.cfg` — pure `requirements.txt` project

## Platform Requirements

**Development:**
- Python 3.10+ (3.11.x strongly recommended)
- Bash shell (`source`, `export`) — WSL2 or Git Bash on Windows; CMD/PowerShell not supported
- Either Ollama running locally OR AWS Bedrock credentials for real LLM calls
- Conformance tests require neither (use `MockLLMClient`)

**Production / Evaluation:**
- No containerization defined
- Graded via `pytest` conformance suites run by instructors against submitted `student_framework/`
- Student code lives entirely in `student_framework/`; framework code in `mia_agents/` is read-only

---

*Stack analysis: 2026-06-17*
