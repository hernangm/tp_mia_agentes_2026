<!-- refreshed: 2026-06-17 -->
# Codebase Structure

**Analysis Date:** 2026-06-17

## Directory Layout

```
tp_mia_agentes_2026/          # repo root
├── mia_agents/               # FIXED — shared framework (do not edit)
│   ├── __init__.py           # public re-exports: Agent, LLMClient, types, tool helpers
│   ├── protocols.py          # Agent and LLMClient structural protocols (typing.Protocol)
│   ├── types.py              # ToolCall, LLMResponse, ToolSchema, AgentStep, AgentResult
│   ├── tool_schema.py        # ToolSchema.from_callable / from_model, final_result helpers
│   ├── llm_client.py         # OllamaProvider, BedrockProvider, LLMClient wrapper
│   ├── _env.py               # .env loader (no clobber, no op:// passthrough)
│   ├── cli.py                # `python -m mia_agents.cli run` entry point
│   └── testing/              # FIXED — test infrastructure
│       ├── __init__.py       # re-exports MockLLMClient, make_recording_tool
│       ├── mock_llm.py       # MockLLMClient: deterministic LLM test double
│       └── tools.py          # RecordingTool, make_recording_tool factory
│
├── student_framework/        # EDITABLE — student implementation lives here
│   ├── __init__.py           # build_agent() factory (only public entry point)
│   ├── agent.py              # MyAgent class: register_tool, run, structured_call
│   └── tools/                # one file per tool (or grouped as preferred)
│       ├── __init__.py
│       └── example.py        # illustrative reverse_string tool (can be deleted)
│
├── tests/
│   ├── conformance/          # FIXED — immutable milestone contracts
│   │   ├── __init__.py
│   │   ├── test_m1.py        # M1: single-turn loop, tool registration, AgentStep
│   │   ├── test_m2.py        # M2: statefulness, bounded history, structured_call
│   │   └── test_m3_world.py  # M3: world simulation tools and scenario loader
│   ├── test_bedrock_provider.py   # unit tests for BedrockProvider (mocked boto3)
│   ├── test_ollama_provider.py    # unit tests for OllamaProvider (mocked ollama SDK)
│   └── test_tool_schema.py        # unit tests for ToolSchema.from_callable
│
├── scripts/
│   └── bedrock_llm_smoke.py  # manual smoke test against a real Bedrock endpoint
│
├── .planning/
│   └── codebase/             # GSD codebase map documents
│
├── ENUNCIADO_M1.md           # M1 milestone specification (authoritative contract)
├── README.md                 # setup guide, milestone overview, CLI usage
└── requirements.txt          # ollama>=0.4.0, boto3>=1.34.0, pydantic>=2.0.0, pytest>=8.0.0
```

## Directory Purposes

**`mia_agents/`:**
- Purpose: Fixed framework providing shared contracts, types, provider adapters, and test infrastructure
- Contains: Protocols, dataclasses, two LLM provider implementations, schema-generation utilities, env loader, CLI runner, test doubles
- Key files: `protocols.py`, `types.py`, `llm_client.py`, `tool_schema.py`
- Rule: Students must not modify anything here; evaluator re-applies original files

**`mia_agents/testing/`:**
- Purpose: Deterministic testing utilities shared by all conformance tests
- Contains: `MockLLMClient` (replays pre-programmed `LLMResponse` objects), `RecordingTool` (records invocations and returns fixed value)
- Key files: `mock_llm.py`, `tools.py`

**`student_framework/`:**
- Purpose: Student-owned implementation package; the only place students write production code
- Contains: `build_agent` factory, `MyAgent` class, tool definitions
- Key files: `__init__.py` (factory, public API), `agent.py` (core logic)

**`student_framework/tools/`:**
- Purpose: One Python module per tool (or grouped) with callable + `ToolSchema`
- Contains: Tool functions annotated with `Annotated[..., Field(...)]`, auto-generated schemas via `ToolSchema.from_callable`
- Key files: `example.py` (template to copy from; can be deleted once real tools are added)

**`tests/conformance/`:**
- Purpose: Immutable milestone contracts; define the exact pass/fail criteria evaluated by instructors
- Contains: Three test modules, one per milestone
- Rule: Students must not modify these files; any divergence causes milestone failure

**`tests/` (root-level test files):**
- Purpose: Unit tests for specific framework components (provider format translation, schema generation)
- Contains: `test_bedrock_provider.py`, `test_ollama_provider.py`, `test_tool_schema.py`

**`scripts/`:**
- Purpose: Manual developer utilities (not run in CI)
- Key files: `bedrock_llm_smoke.py` — quick sanity check against a live Bedrock endpoint

## Key File Locations

**Entry Points:**
- `student_framework/__init__.py`: `build_agent(config)` — sole entry point for CLI and all tests
- `mia_agents/cli.py`: `main()` — `python -m mia_agents.cli run --module ... --message ...`

**Contracts / Types:**
- `mia_agents/protocols.py`: `Agent` and `LLMClient` Protocol definitions
- `mia_agents/types.py`: `ToolCall`, `LLMResponse`, `ToolSchema`, `AgentStep`, `AgentResult`

**Schema Generation:**
- `mia_agents/tool_schema.py`: `tool_schema_from_callable`, `final_result_tool_schema`, `FINAL_RESULT_TOOL_NAME`

**LLM Providers:**
- `mia_agents/llm_client.py`: `OllamaProvider`, `BedrockProvider`, `LLMClient.from_env()`

**Student Implementation:**
- `student_framework/agent.py`: `MyAgent` — implement `register_tool`, `run`, `structured_call` here
- `student_framework/__init__.py`: `build_agent` — register all tools here

**Testing Infrastructure:**
- `mia_agents/testing/mock_llm.py`: `MockLLMClient`
- `mia_agents/testing/tools.py`: `make_recording_tool`, `RecordingTool`

**Milestone Contracts:**
- `tests/conformance/test_m1.py`: M1 conformance suite
- `tests/conformance/test_m2.py`: M2 conformance suite
- `tests/conformance/test_m3_world.py`: M3 world-simulation conformance suite

**Specifications:**
- `ENUNCIADO_M1.md`: Authoritative M1 contract (canonical, more complete than tests alone)
- `README.md`: Setup instructions and milestone-by-milestone development guide

## Naming Conventions

**Files:**
- Snake_case module names: `llm_client.py`, `tool_schema.py`, `mock_llm.py`
- Private/internal modules prefixed with `_`: `_env.py`
- Test files prefixed with `test_`: `test_m1.py`, `test_tool_schema.py`
- Conformance tests named `test_<milestone>.py`

**Classes:**
- PascalCase: `MyAgent`, `LLMClient`, `OllamaProvider`, `BedrockProvider`, `MockLLMClient`, `RecordingTool`
- Dataclasses follow same PascalCase: `ToolCall`, `LLMResponse`, `ToolSchema`, `AgentStep`, `AgentResult`

**Functions:**
- Snake_case: `build_agent`, `register_tool`, `make_recording_tool`, `load_env_files`, `tool_schema_from_callable`
- Factory classmethods: `ToolSchema.from_callable`, `ToolSchema.from_model`, `LLMClient.from_env`

**Constants:**
- UPPER_SNAKE_CASE: `FINAL_RESULT_TOOL_NAME` (`mia_agents/tool_schema.py`)

**Tool schema instances:**
- Named `<function_name>_schema`: e.g. `reverse_string_schema = ToolSchema.from_callable(reverse_string)` (`student_framework/tools/example.py`)

## Module Organization

**Package `mia_agents`** exports through `__init__.py`:
- Types: `AgentResult`, `AgentStep`, `LLMResponse`, `ToolCall`, `ToolSchema`
- Protocols: `Agent`, `LLMClient`
- Tool helpers: `FINAL_RESULT_TOOL_NAME`, `final_result_tool_schema`

**Package `mia_agents.testing`** exports through `__init__.py`:
- `MockLLMClient`
- `make_recording_tool`

**Package `student_framework`** exports through `__init__.py`:
- `build_agent` (only symbol tests and CLI ever import)

## Where to Add New Code

**New tool (student):**
- Implementation: `student_framework/tools/<tool_name>.py` — define callable with `Annotated` + `Field` types and docstring; generate schema with `ToolSchema.from_callable`
- Registration: call `agent.register_tool(fn, schema)` inside `build_agent()` in `student_framework/__init__.py`

**New LLM provider (if needed — do not modify `llm_client.py`):**
- Implementation: `student_framework/<provider_name>.py` — implement a class with `chat(...) -> LLMResponse` satisfying `mia_agents.protocols.LLMClient`
- Usage: pass as `build_agent({"llm_client": my_provider_instance})`

**Extended agent behaviour (memory strategy, retry logic, etc.):**
- All changes belong in `student_framework/agent.py` within `MyAgent`

**Additional unit tests (student-authored):**
- Location: `tests/` (root level, alongside `test_tool_schema.py` etc.) — not inside `tests/conformance/` which is immutable

## Special Directories

**`.planning/codebase/`:**
- Purpose: GSD codebase map documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by GSD mapper agent)
- Committed: Yes (planning artifacts)

**`tests/conformance/`:**
- Purpose: Immutable grading contracts
- Generated: No (written by instructors)
- Committed: Yes; must never be modified by students

---

*Structure analysis: 2026-06-17*
