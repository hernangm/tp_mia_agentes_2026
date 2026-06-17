# Testing Patterns

**Analysis Date:** 2026-06-17

## Setup

**Test runner:**
- `pytest` >= 8.0.0 (declared in `requirements.txt`)
- No `pytest.ini`, `setup.cfg`, or `pyproject.toml` found — pytest runs with default discovery settings
- Tests discovered automatically by filename prefix `test_`

**Run commands:**
```bash
pytest                                    # Run all tests
pytest tests/conformance/test_m1.py      # Run M1 conformance tests only
pytest tests/conformance/test_m2.py      # Run M2 conformance tests only
pytest tests/conformance/test_m3_world.py  # Run M3 world simulation tests only
pytest tests/test_tool_schema.py          # Run tool schema unit tests
pytest tests/test_bedrock_provider.py     # Run Bedrock provider tests
pytest tests/test_ollama_provider.py      # Run Ollama provider tests
```

**Dependencies required:**
- `pytest` — test runner
- `pydantic` — used in test assertions and schema fixtures
- `boto3` — mocked in `test_bedrock_provider.py` via `unittest.mock`
- `ollama` — mocked in `test_ollama_provider.py` via `unittest.mock`

## Test Organization

**Directory layout:**
```
tests/
├── __init__.py
├── test_bedrock_provider.py     # Unit tests for BedrockProvider (mocked boto3)
├── test_ollama_provider.py      # Unit tests for OllamaProvider (mocked ollama.Client)
├── test_tool_schema.py          # Unit tests for ToolSchema.from_callable
└── conformance/
    ├── __init__.py
    ├── test_m1.py               # Conformance tests for Milestone 1 (stateless agent loop)
    ├── test_m2.py               # Conformance tests for Milestone 2 (stateful + structured_call)
    └── test_m3_world.py         # Tests for mia_world simulation tools and scenarios
```

**Two test categories:**
1. **Unit tests** (`tests/test_*.py`) — test fixed framework components (providers, schema generation) in isolation with mocked external dependencies
2. **Conformance tests** (`tests/conformance/`) — test the student's `student_framework` against the `Agent` protocol contract using `MockLLMClient`; these must not be modified by students

**Naming:**
- Test functions: `test_<what_is_verified>` in `snake_case`
- Helper builder functions: `_<role>` prefix (private by convention): `_agent_with`, `_converse_response`, `_fake_response`, `_build_study_scenario`, `_tools`

## Patterns

**MockLLMClient — primary mocking strategy:**
The framework provides `mia_agents.testing.MockLLMClient` as the canonical test double for the LLM. It takes a pre-programmed list of `LLMResponse | Exception` objects and returns them in order on each `chat()` call. It records all calls in `self.calls` for assertion.

```python
from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall

mock = MockLLMClient([
    LLMResponse(
        content=None,
        tool_calls=[ToolCall(id="c1", name="examine", arguments='{"target": "alfombra"}')],
    ),
    LLMResponse(content="Encontré una llave."),
])
agent = build_agent({"llm_client": mock})
result = agent.run("explora la sala")
```

**Inspecting what the agent sent to the LLM:**
`mock.calls` is a list of dicts with keys `messages`, `tools`, `system`, `temperature`, `response_format`. Tests assert on these to verify agent behavior:

```python
sent_tools = mock.calls[0]["tools"]
assert schema.name in [t.name if isinstance(t, ToolSchema) else t.get("name") for t in sent_tools]

second_call_payload = str(mock.calls[1]["messages"])
assert "ALFA-7" in second_call_payload
```

**Fixtures (pytest):**
Used in `test_bedrock_provider.py` and `test_ollama_provider.py` to mock external SDK clients:

```python
@pytest.fixture
def fake_client():
    with patch("mia_agents.llm_client.boto3.client") as factory:
        instance = MagicMock()
        factory.return_value = instance
        yield instance

@pytest.fixture
def provider(fake_client) -> BedrockProvider:
    return BedrockProvider(model="amazon.nova-lite-v1:0", region="us-east-1")
```

Fixtures are defined at the module level, not in conftest files.

**`monkeypatch` for environment variables:**
Used to set/unset env vars without polluting the real environment:

```python
def test_constructor_uses_env_when_args_absent(fake_client, monkeypatch) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "foo-model-id")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
```

**`unittest.mock.patch` for SDK mocking:**
Used via context manager in fixtures to replace `boto3.client` and `ollama.Client` at the import path inside the module under test:

```python
with patch("mia_agents.llm_client.boto3.client") as factory:
    ...
with patch("mia_agents.llm_client.ollama.Client") as cls:
    ...
```

**`pytest.raises` for exception testing:**
```python
with pytest.raises(RuntimeError, match="BEDROCK_MODEL_ID"):
    BedrockProvider()

with pytest.raises(Exception):
    agent.structured_call(prompt="dame un objeto", schema=Answer, max_repair_attempts=2)

with pytest.raises(TypeError, match="\\*\\*kwargs"):
    ToolSchema.from_callable(bad)
```

**`pytest.mark.parametrize` for table-driven tests:**
Used in `test_m3_world.py` for error-case coverage of invalid tool inputs and for scenario solution verification:

```python
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("examine", {"target": "fantasma"}),
        ("take", {"item": "fantasma"}),
        ("use", {"item": "fantasma", "target": "puerta_principal"}),
    ],
)
def test_invalid_ids_return_error_strings(tool_name: str, kwargs: dict) -> None:
    world = _build_study_scenario().initial_world
    msg = _tools(world)[tool_name](**kwargs)
    assert isinstance(msg, str)
    assert "Error" in msg
```

**`pytest.mark.skipif` for optional scenario files:**
Used to skip tests when JSON scenario files are not present on disk:

```python
@pytest.mark.skipif(
    not SCENARIO_PATH.exists(),
    reason=f"Escenario no encontrado en {SCENARIO_PATH}",
)
def test_load_scenario_from_disk() -> None:
    ...
```

**Helper builder functions:**
Each test module defines private helpers that build test state to reduce repetition:

```python
def _agent_with(mock: MockLLMClient) -> Agent:
    return build_agent({"llm_client": mock})

def _build_study_scenario() -> Scenario:
    # builds world inline without loading JSON
    ...

def _converse_response(text=None, tool_uses=None, ...) -> dict:
    # builds a boto3 Converse API response dict
    ...
```

**`RecordingTool` for verifying tool invocation:**
Provided in `mia_agents.testing.tools`. Records kwargs from each call and returns a fixed value:

```python
from mia_agents.testing import make_recording_tool

tool, schema = make_recording_tool(return_value="recorded:hola")
agent.register_tool(tool, schema)
result = agent.run("invoca la herramienta")
assert tool.calls == [{"text": "hola"}]
```

**`Annotated` + `Field` for tool parameter descriptions in test helpers:**

```python
def record(
    text: Annotated[str, Field(description="Texto arbitrario para registrar.")],
) -> str:
    return tool(text=text)

schema = ToolSchema.from_callable(record, name=name, description=description)
```

**Return value assertions:**
World tool functions always return strings. Error cases are identified by string content (`"Error" in msg`), not by exceptions. Tests assert on specific substrings:

```python
assert "Tomas" in msg
assert "abre" in msg.lower()
assert "cerrada" in out
assert "Error" in msg
```

**Type assertions:**
Conformance tests verify protocol satisfaction with `isinstance`:

```python
assert isinstance(agent, Agent)
assert isinstance(result, AgentResult)
assert isinstance(parsed, Answer)
```

## Coverage

**What is tested:**

- `mia_agents/llm_client.py` — `BedrockProvider` and `OllamaProvider`: message normalization (user, assistant, tool roles), tool schema formatting, token parsing, `raw_response` passthrough, `response_format` handling, environment variable fallback (`test_bedrock_provider.py`, `test_ollama_provider.py`)
- `mia_agents/tool_schema.py` — `ToolSchema.from_callable`: name, description, parameter schema, required fields, optional fields, full docstring, override args, zero-parameter functions, `**kwargs` rejection (`test_tool_schema.py`)
- `student_framework/` — conformance contract for `Agent.run` (M1: no-loop, tool execution, steps, call count), `Agent` statefulness and history bounding (M2), `structured_call` with `final_result` tool, repair loop, token accounting (`tests/conformance/test_m1.py`, `test_m2.py`)
- `mia_world/` — world tools (`look`, `examine`, `take`, `use`, `go`), scenario loading, goal checking, multi-item locks, locked exits, composite goals (`all_of`, `any_of`, `sequence`), CLI resolver (`test_m3_world.py`)

**What is NOT tested (gaps):**

- `mia_agents/_env.py` — `load_env_files`, `_parse_line`, `_candidate_paths` have no dedicated tests
- `mia_agents/cli.py` — `main` and `_run` are not tested
- `student_framework/agent.py` — `MyAgent` is tested only indirectly through conformance tests; internal implementation details are not unit-tested
- `student_framework/tools/example.py` — `reverse_string` is not tested
- Edge cases for `MockLLMClient` running out of responses (`RuntimeError`) are not tested in the test suite
- No integration tests that call a real LLM (all tests are fully deterministic and offline)
- No performance or load tests
