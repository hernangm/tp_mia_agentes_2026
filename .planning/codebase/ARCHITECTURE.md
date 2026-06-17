<!-- refreshed: 2026-06-17 -->
# Architecture

**Analysis Date:** 2026-06-17

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                              │
│             `mia_agents/cli.py`  /  `mia_world/cli.py`              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ calls build_agent(config)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     student_framework/                               │
│   `student_framework/__init__.py`  →  build_agent() factory          │
│   `student_framework/agent.py`     →  MyAgent (Agent protocol)       │
│   `student_framework/tools/`       →  callable tools + ToolSchema    │
└───────────┬──────────────────────────────┬──────────────────────────┘
            │ depends on protocol types    │ registers tools
            ▼                              ▼
┌───────────────────────────┐   ┌──────────────────────────────────────┐
│      mia_agents/          │   │   mia_world/ (M3 only)               │
│  protocols.py  (Agent,    │   │   state.py, tools.py, scenarios.py,  │
│    LLMClient Protocols)   │   │   goals.py — world simulation tools   │
│  types.py  (ToolSchema,   │   └──────────────────────────────────────┘
│    LLMResponse, AgentStep,│
│    AgentResult, ToolCall) │
│  tool_schema.py           │
│  llm_client.py            │
│    ├── OllamaProvider     │
│    └── BedrockProvider    │
│  _env.py                  │
│  testing/                 │
│    ├── mock_llm.py        │
│    └── tools.py           │
└───────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `build_agent` factory | Sole public entry point; wires LLMClient into MyAgent and registers tools | `student_framework/__init__.py` |
| `MyAgent` | Implements `Agent` protocol: tool registry, `run` loop, `structured_call` | `student_framework/agent.py` |
| Student tools | Callable functions + auto-generated `ToolSchema` objects | `student_framework/tools/` |
| `Agent` Protocol | Structural contract (`register_tool`, `run`, `structured_call`) checked via `isinstance` | `mia_agents/protocols.py` |
| `LLMClient` Protocol | Structural contract for any LLM provider (`chat` method) | `mia_agents/protocols.py` |
| `LLMClient` (concrete) | Provider-selecting wrapper; delegates to `OllamaProvider` or `BedrockProvider` | `mia_agents/llm_client.py` |
| `OllamaProvider` | Translates internal message format to Ollama SDK; synthesizes tool_call IDs | `mia_agents/llm_client.py` |
| `BedrockProvider` | Translates to AWS Converse API; groups consecutive tool results into one user message | `mia_agents/llm_client.py` |
| `ToolSchema` | Data class holding name/description/parameters; generates `to_llm_spec()` dict | `mia_agents/types.py` |
| `tool_schema_from_callable` | Reflects Python function signature into JSON Schema via Pydantic | `mia_agents/tool_schema.py` |
| `final_result_tool_schema` | Builds the synthetic M2 closing tool from a Pydantic BaseModel | `mia_agents/tool_schema.py` |
| `MockLLMClient` | Deterministic test double; replays pre-programmed `LLMResponse` list | `mia_agents/testing/mock_llm.py` |
| `RecordingTool` / `make_recording_tool` | Test fixtures that record invocations and return fixed strings | `mia_agents/testing/tools.py` |
| `load_env_files` | Loads `.env` into `os.environ` without clobbering existing vars or unresolved `op://` refs | `mia_agents/_env.py` |
| Conformance tests | Immutable tests that define the pass/fail contract for each milestone | `tests/conformance/` |
| World simulation (M3) | Room/item state machine, navigation, goal checking, JSON scenario loader | `mia_world/` (not present yet) |

## Pattern Overview

**Overall:** Protocol-based Dependency Injection with a Framework/Plugin split

**Key Characteristics:**
- The codebase is divided into a **fixed framework** (`mia_agents/`) that students must not edit, and a **student plugin** (`student_framework/`) where all implementation lives.
- Both `Agent` and `LLMClient` are `typing.Protocol` with `@runtime_checkable`, so `isinstance` checks work without inheritance.
- Tools are plain Python callables; their JSON Schema is derived automatically from type annotations via `ToolSchema.from_callable`, eliminating manual schema authorship.
- The `MockLLMClient` substitution pattern is the primary testing mechanism: conformance tests inject a deterministic mock via `build_agent({"llm_client": mock})`, making every test API-key-free.
- Real LLM provider selection is driven purely by environment variables (`OLLAMA_HOST` → Ollama, `BEDROCK_MODEL_ID` → Bedrock); no code change is needed to switch providers.

## Layers

**Fixed Framework Layer (`mia_agents/`):**
- Purpose: Provide immutable shared types, protocols, provider implementations and testing infrastructure
- Location: `mia_agents/`
- Contains: Dataclasses (`types.py`), structural protocols (`protocols.py`), two LLM provider adapters, schema introspection utilities, env loader, test doubles
- Depends on: `pydantic`, `ollama`, `boto3`
- Used by: `student_framework/`, `tests/`

**Student Implementation Layer (`student_framework/`):**
- Purpose: Concrete `Agent` implementation students must write to pass conformance tests
- Location: `student_framework/`
- Contains: `MyAgent` class, `build_agent` factory, tool definitions
- Depends on: `mia_agents` (protocols + types only — never `llm_client` internals)
- Used by: `mia_agents/cli.py`, `tests/conformance/`

**Conformance Test Layer (`tests/conformance/`):**
- Purpose: Define the exact observable contract for M1, M2, M3 milestones
- Location: `tests/conformance/`
- Contains: `test_m1.py`, `test_m2.py`, `test_m3_world.py` — all immutable
- Depends on: `mia_agents.testing`, `student_framework.build_agent`
- Used by: CI / evaluators

**World Simulation Layer (`mia_world/`):**
- Purpose: Room-and-item escape-room engine for M3 evaluation (referenced by `test_m3_world.py` but package not present in scaffold)
- Location: `mia_world/` (expected at repo root, alongside `scenarios/`)
- Contains: `state.py`, `tools.py` (`look/examine/take/use/go`), `scenarios.py`, `goals.py`, CLI
- Depends on: `mia_agents` types
- Used by: `tests/conformance/test_m3_world.py`, `mia_world/cli.py`

## Data Flow

### M1 — Single-turn agent loop

1. CLI or test calls `build_agent(config)` → `student_framework/__init__.py`
2. `build_agent` instantiates `MyAgent(llm_client=...)` and calls `register_tool(fn, schema)` for each tool — `student_framework/agent.py`
3. `agent.run(user_message)` starts; builds `messages = [{"role": "user", "content": user_message}]`
4. `self._llm.chat(messages, tools=list(self._schemas.values()), system=self._system)` → `mia_agents/llm_client.py`
5. `LLMClient.chat` delegates to `OllamaProvider.chat` or `BedrockProvider.chat`
6. Provider normalises messages to its native format, calls vendor SDK, returns `LLMResponse(content, tool_calls, input_tokens, output_tokens, raw_response)`
7. **If `tool_calls` present:** agent parses `arguments` (JSON string → dict), calls `self._tools[name](**kwargs)` → returns `str`, records `AgentStep`, appends tool result as `role: "tool"` message, loops back to step 4
8. **If no `tool_calls`:** agent returns `AgentResult(answer=resp.content, steps=[...])` — terminates

### M2 — Stateful multi-turn conversation

Same as M1 but `run` accumulates `messages` across calls to the same `MyAgent` instance.
History is bounded: `len(messages)` sent to `chat()` must never exceed `max_history_messages`.

### M2 — `structured_call` with `final_result`

1. `agent.structured_call(prompt, schema)` called with a Pydantic `BaseModel` subclass
2. Agent constructs `final_result_tool_schema(schema)` — `mia_agents/tool_schema.py`
3. Calls `self._llm.chat(messages, tools=[final_result_tool_schema])` — only this synthetic tool is offered
4. LLM must respond with a `tool_call` to `final_result`; agent validates `arguments` via `schema.model_validate(...)`
5. On validation failure: retry with repair context up to `max_repair_attempts` times
6. Returns validated `schema` instance or raises after exhausting retries

**State Management:**
- M1: no persistent state; each `run` is independent
- M2: `MyAgent` holds a `messages: list[dict]` accumulating across `run` calls; management strategy (sliding window, summary, etc.) is the student's responsibility

## Key Abstractions

**`Agent` Protocol (`mia_agents/protocols.py`):**
- Purpose: Structural interface that every student submission must satisfy
- Pattern: `@runtime_checkable` `typing.Protocol` — verified with `isinstance(agent, Agent)` in conformance tests
- Methods: `register_tool(callable, ToolSchema)`, `run(str) -> AgentResult`, `structured_call(str, type, int) -> T`

**`LLMClient` Protocol (`mia_agents/protocols.py`):**
- Purpose: Swappable LLM backend interface
- Pattern: `@runtime_checkable` `typing.Protocol` — real provider and mock implement same `chat` signature
- Used by: `MyAgent.__init__`, injected via `build_agent({"llm_client": ...})`

**`ToolSchema` dataclass (`mia_agents/types.py`):**
- Purpose: Portable tool descriptor; decouples Python callables from provider-specific JSON formats
- Pattern: data object with factory classmethods (`from_callable`, `from_model`) and output method `to_llm_spec()`
- Lifecycle: created in `student_framework/tools/*.py`, stored in `MyAgent`, serialised inside `_BaseLLMProvider._format_tools()`

**`build_agent` factory (`student_framework/__init__.py`):**
- Purpose: Single public entry point for CLI and conformance tests
- Pattern: factory function accepting optional `config` dict; respects `config["llm_client"]` for mock injection

## Entry Points

**CLI runner:**
- Location: `mia_agents/cli.py`, invoked as `python -m mia_agents.cli run --module student_framework --message "..."`
- Triggers: `importlib.import_module(module_name).build_agent()` then `agent.run(message)`
- Responsibilities: Argument parsing, printing `AgentResult` as JSON

**Conformance tests:**
- Location: `tests/conformance/test_m1.py`, `test_m2.py`, `test_m3_world.py`
- Triggers: `pytest tests/conformance/`
- Responsibilities: Inject `MockLLMClient`, call `build_agent`, assert protocol invariants

## Architectural Constraints

- **Fixed vs editable:** Everything in `mia_agents/` is read-only for students. The evaluator re-runs original files; modifications there will diverge and fail milestones.
- **Dependency direction:** `student_framework/` imports from `mia_agents` (types, protocols); `mia_agents` never imports from `student_framework`. This is a strict one-way dependency.
- **No LLM logic in `llm_client.py`:** All agent behaviour (loops, retry, memory, validation) must live in `student_framework/agent.py`. Logic in `llm_client.py` is invisible to `MockLLMClient` and therefore untestable.
- **Tool callables must return `str`:** The protocol requires `Callable[..., str]`. Non-string returns will break the message history assembly.
- **`arguments` field is always a JSON string:** `ToolCall.arguments` is `str` (JSON-encoded); the agent is responsible for `json.loads(arguments)` before calling the tool.
- **Provider format normalisation:** `OllamaProvider` synthesises `tool_call_id` (Ollama doesn't emit one); `BedrockProvider` groups consecutive `role: "tool"` messages into a single `role: "user"` block (Converse API requirement).
- **`response_format` not supported by Bedrock:** `BedrockProvider.chat` accepts the parameter but ignores it. `structured_call` must use the `final_result` tool pattern instead.
- **Global singleton `_LOADED` in `_env.py`:** `load_env_files` is idempotent by module-level flag; re-entrant calls are no-ops unless `force=True`.

## Anti-Patterns

### Implementing agent logic inside `llm_client.py`

**What happens:** A student adds retry logic, tool dispatch, or history management inside `OllamaProvider` or `BedrockProvider`.
**Why it's wrong:** Conformance tests replace the provider with `MockLLMClient`. Any logic inside the provider is never exercised by tests and will not be credited.
**Do this instead:** All loops, retries, and state management belong in `student_framework/agent.py`.

### Building `ToolSchema.parameters` by hand

**What happens:** A student writes `ToolSchema(name="calc", description="...", parameters={"type": "object", "properties": {...}})` manually.
**Why it's wrong:** Manual schemas drift from the actual function signature and are verbose and error-prone.
**Do this instead:** Use `ToolSchema.from_callable(fn)` which derives the JSON Schema from Python type annotations automatically (`mia_agents/tool_schema.py`).

### Importing `LLMClient` (concrete class) instead of using the injected one

**What happens:** `MyAgent.__init__` calls `LLMClient.from_env()` unconditionally.
**Why it's wrong:** Conformance tests pass a mock via `config["llm_client"]`; if the agent ignores it, tests call a real API (or fail due to missing credentials).
**Do this instead:** Accept `llm_client` as a constructor argument and use it — as scaffolded in `student_framework/__init__.py` (`llm = config.get("llm_client") or LLMClient.from_env()`).

### Using `final_result` in the `run` loop (M1)

**What happens:** A student offers `final_result` as a regular tool inside `run`.
**Why it's wrong:** M1 loop must terminate on plain text response (no `tool_calls`). M2 `structured_call` uses `final_result` in isolation; mixing the two breaks test contracts for both milestones.
**Do this instead:** Keep `run` termination on text-only response; implement `final_result` only inside `structured_call` (M2).

## Error Handling

**Strategy:** Return-based error reporting for tools; exception propagation for structural failures.

**Patterns:**
- Tool callables return descriptive error strings (e.g., `"Error: item not found"`) rather than raising exceptions — required by the world simulation tools and implied by M1 robustness contract (unknown tool names must not crash `run`).
- Unknown tool names from LLM hallucinations: agent records an `AgentStep` with `error` set (not `None`) and continues the loop.
- `MockLLMClient` raises `RuntimeError` if `chat()` is called more times than there are programmed responses — surfaces agent loop bugs immediately in tests.
- `structured_call` raises a clean exception after exhausting `max_repair_attempts`; it must never return `None` or a partial result.

## Cross-Cutting Concerns

**Logging:** None in the fixed framework. Students may add logging in `student_framework/`.
**Validation:** Pydantic used inside `tool_schema.py` to build `BaseModel` from function signatures; used in `structured_call` via `schema.model_validate(arguments)`.
**Authentication:** LLM credentials via environment variables only (`OLLAMA_HOST`, `BEDROCK_MODEL_ID`, `AWS_*`). Loaded lazily by `mia_agents/_env.py:load_env_files()` when `LLMClient.from_env()` is first called.

---

*Architecture analysis: 2026-06-17*
