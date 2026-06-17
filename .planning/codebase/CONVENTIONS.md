# Coding Conventions

**Analysis Date:** 2026-06-17

## Naming

**Files:**
- Modules use `snake_case`: `llm_client.py`, `tool_schema.py`, `mock_llm.py`
- Private/internal modules prefixed with underscore: `_env.py`
- Test files prefixed with `test_`: `test_m1.py`, `test_bedrock_provider.py`

**Classes:**
- `PascalCase` throughout: `MyAgent`, `MockLLMClient`, `RecordingTool`, `OllamaProvider`, `BedrockProvider`, `LLMClient`, `ToolSchema`, `AgentResult`, `AgentStep`, `LLMResponse`, `ToolCall`
- Abstract base classes prefixed with underscore: `_BaseLLMProvider`

**Functions and methods:**
- `snake_case` for all functions and methods: `build_agent`, `register_tool`, `from_callable`, `to_llm_spec`, `load_env_files`
- Private helpers prefixed with underscore: `_run`, `_pick`, `_arguments_to_dict`, `_parse_line`, `_candidate_paths`, `_normalize_messages`, `_wrap_tool_spec`, `_format_tools`, `_tool_specs_as_dicts`
- Factory classmethods named `from_*`: `from_callable`, `from_model`, `from_env`

**Variables:**
- `snake_case` for all variables: `tool_calls`, `raw_response`, `input_tokens`, `llm_client`, `system_prompt`, `max_iterations`
- Private instance attributes prefixed with underscore: `self._llm`, `self._system`, `self._model`, `self._client`, `self._responses`
- Module-level constants in `UPPER_SNAKE_CASE`: `FINAL_RESULT_TOOL_NAME`, `_LOADED`
- Type alias variables in `PascalCase`: `ToolSpecInput`

**Parameters:**
- Parameters matching protocol names are kept consistent across the codebase: `messages`, `tools`, `system`, `temperature`, `response_format`

## Code Style

**Indentation:**
- 4 spaces (Python standard)

**Line length:**
- No explicit config found; lines in practice stay under ~100 characters

**Imports:**
- `from __future__ import annotations` at the top of every module — used universally
- Standard library imports first, then third-party (`pydantic`, `boto3`, `ollama`), then local (`mia_agents.*`)
- Specific imports preferred over star imports
- Type-only imports are not separated into `TYPE_CHECKING` blocks; `annotations` future import makes forward references work

**Type annotations:**
- Full type annotations on all function signatures and return types
- `-> None` annotated explicitly
- Use of `Any` from `typing` where dynamic structures are needed
- Union types use the `X | Y` syntax (Python 3.10+ style), relying on `from __future__ import annotations`
- `list[dict[str, Any]]` over `List[Dict[str, Any]]` (modern lowercase generics)

**Dataclasses:**
- Used for all value objects: `ToolCall`, `LLMResponse`, `ToolSchema`, `AgentStep`, `AgentResult` in `mia_agents/types.py`
- `field(default_factory=list)` used for mutable default fields
- No `__post_init__`, no `frozen=True` — plain mutable dataclasses

**Protocols:**
- `typing.Protocol` with `@runtime_checkable` used for structural interfaces: `Agent`, `LLMClient` in `mia_agents/protocols.py`

## Patterns

**Dependency injection:**
- `LLMClient` is injected into `MyAgent.__init__` via `llm_client` parameter
- `build_agent(config)` reads `config["llm_client"]` if present; falls back to `LLMClient.from_env()`
- This pattern enables test substitution via `MockLLMClient` without any patching

**Protocol-based duck typing:**
- Framework uses `Protocol` classes, not abstract base classes, for the public contracts (`Agent`, `LLMClient`)
- `MockLLMClient` satisfies `LLMClient` protocol without inheritance

**Factory methods:**
- `ToolSchema.from_callable(fn)` derives schema from Python type hints and docstrings
- `ToolSchema.from_model(model, name=..., description=...)` derives schema from a Pydantic `BaseModel`
- `LLMClient.from_env()` selects provider (Ollama or Bedrock) based on environment variables

**Tool registration pattern:**
- Tools are registered as `(callable, ToolSchema)` pairs via `agent.register_tool(fn, schema)`
- Schema generation: annotate parameters with `Annotated[type, Field(description="...")]`, write a docstring, call `ToolSchema.from_callable(fn)`
- Example in `student_framework/tools/example.py`

**Message history format:**
- Internal message format is a list of dicts with `role`, `content`, and optionally `tool_calls` / `tool_call_id` keys
- Provider-specific normalization happens inside `_normalize_messages` static methods in each provider class

**Module boundaries:**
- `mia_agents/` is the fixed framework — not to be edited by students
- `student_framework/` is the student-editable implementation zone
- Entry point is always `build_agent(config) -> Agent` in `student_framework/__init__.py`

**`__all__` usage:**
- Explicitly defined in `mia_agents/__init__.py` and `mia_agents/testing/__init__.py` to control public API surface

## Documentation

**Docstring style:**
- Google/NumPy hybrid: most docstrings use plain prose paragraphs without formal sections, but `MyAgent.__init__` uses `Parameters\n----------` NumPy style
- Example: `mia_agents/agent.py` `__init__` uses NumPy-style parameter docs; most other functions use single-paragraph prose

**Docstring content:**
- Module-level docstrings explain purpose, constraints, and usage examples (see `llm_client.py`, `mock_llm.py`)
- Class docstrings describe the role, key behavior, and relevant environment variables
- Method docstrings describe contracts, not implementation details
- Docstrings for tool functions are consumed by `ToolSchema.from_callable` and become the LLM-facing tool description — they must be clear and complete

**Comments:**
- Inline comments (`#`) used for non-obvious logic, particularly in provider message normalization
- Section dividers `# -- internos ---` used inside classes to group private methods
- `# TODO (M1):` and `# TODO (M2):` markers used in student skeleton files to guide implementation

**Language:**
- Docstrings and comments are written in Spanish throughout the codebase
- Variable names and code identifiers are in English
