# Concerns

**Analysis Date:** 2026-06-17

---

## Incomplete Implementations

The entire student deliverable is unimplemented. Every method in the student area raises `NotImplementedError`. The project is at skeleton/scaffold state.

**`student_framework/agent.py` — `MyAgent.__init__`:**
- Issue: Two TODO comments mark missing internal state initialization.
- `# TODO (M1): inicializa el estado interno para las herramientas registradas.`
- `# TODO (M2): inicializa la estructura de historial conversacional.`
- Impact: The agent cannot store tools or conversation history. All conformance tests will fail immediately.
- Fix: Add `self._tools: dict[str, Callable] = {}` and `self._schemas: dict[str, ToolSchema] = {}` in `__init__`, and a `self._history: list[dict] = []` for M2.

**`student_framework/agent.py` — `MyAgent.register_tool`:**
- Issue: `raise NotImplementedError("M1: implementa el registro de herramientas")` — body is a stub.
- Impact: `test_register_tool_signature` and `test_tool_is_executed_when_called` in `tests/conformance/test_m1.py` will fail.
- Fix: Store `tool` and `schema` in `self._tools` and `self._schemas` dicts keyed by `schema.name`.

**`student_framework/agent.py` — `MyAgent.run`:**
- Issue: `raise NotImplementedError("M1: implementa el bucle del agente")` — body is a stub.
- Impact: All M1 conformance tests fail. All M2 tests that call `run` fail. CLI cannot be used.
- Fix: Implement the agent loop: call `self._llm.chat(messages=..., tools=list(self._schemas.values()), system=self._system)`, handle `tool_calls`, build `AgentStep` records, enforce `max_iterations`, return `AgentResult`.

**`student_framework/agent.py` — `MyAgent.structured_call`:**
- Issue: `raise NotImplementedError("M2: implementa salida estructurada con reparación")` — stub for M2.
- Impact: All M2 `structured_call` conformance tests (`test_structured_call_offers_final_result_tool`, `test_structured_output_max_retries`, `test_structured_output_repairs_schema_validation_error`) fail.
- Fix: Implement with synthetic `final_result` tool using `mia_agents.tool_schema.final_result_tool_schema(schema)`, retry loop up to `max_repair_attempts`, raise exception if all retries exhausted.

**`student_framework/__init__.py` — `build_agent`:**
- Issue: The TODO comment `# TODO (M1): instancien su agente y llamen a agent.register_tool(...)` is unresolved. The example `register_tool` call is commented out. No real tools are registered.
- Impact: Even when `run` is implemented, no tools will be available unless this is completed.
- Fix: Import and register the three mandatory tools (calculator, file reader, free tool) before returning the agent.

**`student_framework/tools/__init__.py`:**
- Issue: File only contains a docstring listing the three required tools. No implementations exist.
- Impact: No tools are available. Conformance tests requiring tool execution cannot pass.
- Fix: Implement three callables with `Annotated` + `Field` signatures and `ToolSchema.from_callable(...)` schemas.

---

## Assignment Gaps

**M1 — Three mandatory tools not implemented:**
The assignment (`ENUNCIADO_M1.md`) requires exactly three tools. None exist in `student_framework/tools/`:
1. **Calculator** (`calculator`): two numeric operands + operator (`+`, `-`, `*`, `%`) → `str`. Must not use `eval`. Only `example.py` in the scaffold has a reference implementation skeleton (in `tests/test_tool_schema.py`) but it returns `str(left_operand)` — a non-functional stub.
2. **File reader** (`file_reader`): path → UTF-8 text file contents. Not implemented.
3. **Free tool** (any choice): not implemented.

**M1 — No own test scenarios:**
`ENUNCIADO_M1.md` and `README.md` both require "escenarios de prueba propios donde el agente use al menos dos herramientas." No such files or test scripts exist.

**M1 — Written report not present:**
`ENUNCIADO_M1.md` mandates a written report with: architecture diagram, tool interface design, loop termination explanation, and known limitations. No report file is present in the repository.

**M2 — Stateful conversation not implemented:**
`MyAgent.run` has no persistent message history between calls. `test_agent_is_stateful_across_runs` in `tests/conformance/test_m2.py` will fail.

**M2 — Bounded history not implemented:**
`max_history_messages` is accepted in `__init__` but the docstring explicitly states it is ignored in M1. `test_bounded_history_growth` in `tests/conformance/test_m2.py` will fail.

**M2 — Token accounting not implemented:**
`AgentResult.input_tokens` and `AgentResult.output_tokens` are not accumulated from `LLMResponse` objects. `test_token_accounting` and `test_token_accounting_treats_missing_values_as_zero_after_first_report` in `tests/conformance/test_m2.py` will fail.

**M2 — `ENUNCIADO_M2.md` is missing:**
`README.md` references `ENUNCIADO_M2.md` as the authoritative M2 specification, but the file does not exist in the repository. Students cannot read the full M2 contract.

**M3 — Entire infrastructure missing:**
The `mia_world/` package (world simulator, `look`/`examine`/`take`/`use`/`go` tools, `check_goal`, scenario loader, CLI) is referenced extensively in `README.md`, `tests/conformance/test_m3_world.py`, and `ENUNCIADO_M1.md`, but the directory does not exist. All 30+ tests in `test_m3_world.py` will crash on import (`from mia_world import ...`).

**M3 — `scenarios/` directory is missing:**
JSON scenario files (`01-study-with-key.json` through `08-extreme-backtracking-vault.json`) are expected by `test_m3_world.py` but the `scenarios/` directory does not exist. Parametrized scenario tests will either be skipped or fail.

**M3 — `ENUNCIADO_M3.md` is missing:**
`README.md` references `ENUNCIADO_M3.md` for the full M3 specification. The file does not exist.

---

## Known Issues

**All M1 conformance tests will fail with `NotImplementedError`:**
Running `pytest tests/conformance/test_m1.py` will fail at first test that exercises `run` or `register_tool`. The scaffolding design intentionally starts here, but it is an immediate blocker.

**All M3 conformance tests will fail with `ImportError`:**
`tests/conformance/test_m3_world.py` line 18: `from mia_world import (Item, Room, Scenario, World, ...)`. Since `mia_world/` does not exist, the entire test module fails to import. Running `pytest tests/conformance/test_m3_world.py` will error on collection.

**`mia_agents/cli.py` not reviewed — potential import issues:**
The CLI at `mia_agents/cli.py` is part of the scaffold (marked FIJO). It imports `build_agent` from the student module. With all student methods raising `NotImplementedError`, any CLI invocation will fail at runtime. Smoke-testing the CLI requires M1 to be implemented first.

---

## Technical Debt

**Calculator stub in `tests/test_tool_schema.py`:**
The file `tests/test_tool_schema.py` defines a `calculator` function (lines 13-19) solely for schema generation testing. Its body is `return str(left_operand)` — it does not perform any arithmetic. This is intentional test scaffolding, but a student might confuse it for a reference implementation. The real calculator must be implemented in `student_framework/tools/`.

**Commented-out example registration in `student_framework/__init__.py`:**
Lines 39-41 show a commented-out `register_tool` call for `reverse_string`. This dead code should be removed once real tools are registered.

**`student_framework/tools/example.py` must be kept or removed intentionally:**
The docstring states "pueden borrarlo cuando las tres estén listas." Its presence alongside an empty `tools/__init__.py` creates confusion about what is implemented vs. what is only illustrative.

---

## Risks

**Test suite coverage is incomplete by design:**
`test_m1.py` and `test_m2.py` both contain the warning "estos tests deben pasar para aprobar el M1/M2, pero no son la lista completa: la corrección ejecuta además otros casos sobre el mismo contrato." The grading environment runs additional undisclosed test cases. Passing only the provided tests is not sufficient for full credit.

**File reader tool: path traversal risk:**
The assignment requires a `file_reader` tool that reads arbitrary file paths passed by the LLM. A naive implementation with no path restriction would allow the LLM (or a prompt injection) to read any file on the system. The assignment says "acceso acotado" (restricted access) but provides no enforcement mechanism. Students must add sandboxing (e.g., restrict to a specific base directory) or the tool becomes a security risk.

**Calculator tool: operator validation:**
The assignment forbids `eval` and limits operators to `+`, `-`, `*`, `%`. Without explicit validation, the LLM could pass unexpected operator strings. The implementation must whitelist operators explicitly.

**No error handling in agent loop:**
The agent specification requires that unknown tool names return an `AgentStep` with `error` set (not raise an exception). This edge case is explicitly tested in the contract described in `ENUNCIADO_M1.md` ("herramienta desconocida") but has no implementation yet.

**M2 memory strategy not specified:**
`max_history_messages` must be enforced, but the README and assignment intentionally leave the memory management strategy open ("ventana deslizante, resumen, recuperación"). A naive sliding window that drops the oldest messages could silently corrupt multi-turn conversations (e.g., the initial user message disappears). The test `test_bounded_history_growth` only checks message count, not correctness.

**`mia_world` and scenarios must be provided by course staff:**
The README describes `mia_world/` and `scenarios/` as "FIJO (no editar)" — fixed scaffolding that students should not modify. These directories are absent from the current repository state, meaning the course staff has not yet distributed the M3 components. M3 work cannot begin until these are added.

---

## Recommendations

1. **Implement M1 first, in order.** The natural implementation sequence is:
   - Add `self._tools` and `self._schemas` dicts in `MyAgent.__init__`.
   - Implement `register_tool` to populate those dicts.
   - Implement `run` with the agent loop.
   - Implement the three required tools in `student_framework/tools/`.
   - Register tools in `build_agent` inside `student_framework/__init__.py`.
   - Run `pytest tests/conformance/test_m1.py` to verify.

2. **Add path sandboxing to the file reader.** Restrict readable paths to a specific allowed directory (e.g., a `data/` subdirectory). Reject paths containing `..` or absolute paths outside the allowed root.

3. **Verify `mia_world` delivery.** Confirm with course staff when `mia_world/`, `scenarios/`, `ENUNCIADO_M2.md`, and `ENUNCIADO_M3.md` will be distributed. M2 and M3 work is blocked until these arrive.

4. **Read the full contract before implementing.** `ENUNCIADO_M1.md` describes edge cases (unknown tool names, max iterations cutoff, empty string input, steps list for no-tool runs) that are tested by the grader but not covered by the four tests in `test_m1.py`. Implement against the full specification document, not just the provided tests.

5. **Do not implement `structured_call` (M2) until M1 is passing.** The methods are independent but M2 depends on a working agent loop from M1.

6. **Remove `student_framework/tools/example.py` after implementing real tools.** Leaving it risks importing or registering `reverse_string` accidentally; it is not one of the three required tools.

---

*Concerns audit: 2026-06-17*
