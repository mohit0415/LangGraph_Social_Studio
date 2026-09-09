# Testing

268 tests — **208 unit**, **60 integration** — at **99.4% coverage**. No network, no API key,
no Ollama, no real LLM call. A full run takes about 6 seconds.

## Install the test dependencies

```bash
cd backend
uv sync --extra dev
```

or with plain pip:

```bash
cd backend
pip install -e ".[dev]"
```

## Run everything

```bash
cd backend
uv run pytest
```

## Run only the unit tests

```bash
uv run pytest -m unit
```

## Run only the integration tests

```bash
uv run pytest -m integration
```

The markers are applied automatically by directory in `tests/conftest.py`, so anything under
`tests/unit/` is a unit test and anything under `tests/integration/` is an integration test.
Nothing has to be marked by hand.

## Coverage

```bash
uv run pytest --cov --cov-report=term-missing
```

The `Missing` column lists the exact uncovered line numbers.

HTML report, which is the one to open when you want to click through the source:

```bash
uv run pytest --cov --cov-report=html
open htmlcov/index.html
```

Coverage for one half of the suite only:

```bash
uv run pytest -m unit --cov --cov-report=term-missing
uv run pytest -m integration --cov --cov-report=term-missing
```

Fail the build if coverage drops below a threshold:

```bash
uv run pytest --cov --cov-fail-under=95
```

## Useful flags

```bash
uv run pytest -v                                  # one line per test name
uv run pytest -x                                  # stop at the first failure
uv run pytest --lf                                # re-run only what failed last time
uv run pytest tests/unit/test_thread_store.py     # one file
uv run pytest -k "store or refine"                # match test names
uv run pytest --durations=10                      # the ten slowest tests
```

## Always run through `uv run`

`uv run pytest` guarantees the project virtualenv is used. A bare `pytest` resolves through
`PATH`, which on macOS often finds a globally installed pytest from the python.org framework
build instead — and that interpreter has none of this project's dependencies.

The symptom is an import error naming a package you know is installed:

```
ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'
  /Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/importlib/__init__.py
```

The path in the traceback is the tell. This project's venv is Python **3.12**, so any
traceback mentioning 3.13 is running outside it. Check which one you are about to get:

```bash
which pytest              # should be ./.venv/bin/pytest
uv run which pytest       # always the venv one
uv run python -V          # Python 3.12.x
```

Equivalent alternatives if you prefer not to type `uv run`:

```bash
source .venv/bin/activate && python -m pytest
./.venv/bin/pytest
```

In VS Code, the integrated terminal can display a `(backend)` prompt from an earlier
activation while `PATH` still resolves `pytest` elsewhere. Run
**Python: Select Interpreter** and pick `backend/.venv/bin/python` so the Testing panel and
the terminal agree.

## Why `-m unit` fails when only an integration module is broken

Marker filtering happens *after* collection. pytest imports every module under `testpaths`
before it deselects anything, so one unimportable file stops the whole run — which is why
`pytest -m unit` and `pytest -m integration` both died on `test_graph_flow.py` with the same
single error. It is one environment problem, not two test problems.

## Layout

```
tests/
├── conftest.py                      shared fixtures, auto-marking, the fake LLM
├── unit/
│   ├── test_agent_calls.py          ask / ask_structured / write_post / self_critique / route_message
│   ├── test_agent_helpers.py        check_length, _is_ok, _is_malformed, _messages
│   ├── test_llms_cache.py           _read_cache_usage and the HIT/MISS logging
│   ├── test_llms_models.py          get_model, _build_azure, the Ollama probe, model_for
│   ├── test_llms_routing.py         the complexity heuristic and tier pinning
│   ├── test_prompts.py              SHARED_PREFIX, the cache-floor guard, template rendering
│   ├── test_state_and_routing.py    merge_drafts, the reducers, after_self_check, fan_out
│   ├── test_thread_store.py         every ThreadStore method against in-memory SQLite
│   └── test_trace_and_models.py     trace events, SocialInput, RefineIntent, preview
└── integration/
    ├── test_api.py                  every FastAPI endpoint through TestClient
    ├── test_graph_flow.py           the compiled LangGraph end to end
    └── test_nodes.py                each node with its real neighbours
```

## How the LLM is faked

Every model call in the app funnels through exactly two functions — `src.agent.ask` and
`src.agent.ask_structured`. The `studio` fixture patches those two, and that is the whole
mock. Nothing else needs stubbing, no HTTP is intercepted, and no key is read.

The fixture is scriptable, so a test states the scenario and asserts the consequence:

```python
def test_a_rejected_draft_is_revised_and_re_checked(studio, graph):
    studio.set_verdicts("x", ["Replace the opening line.", "OK"])
    ...
```

`tests/unit/test_agent_calls.py` is the exception — it tests `ask` and `ask_structured`
themselves, so it patches `model_for` one level lower and passes in a fake client.

## What the integration tests actually prove

- Three posts are written in parallel from a single brief.
- A rejected draft is revised and re-checked, and **only** that platform is rewritten.
- The loop stops at `MAX_ATTEMPTS` and ships the draft marked `accepted_as_is`.
- An over-length draft is caught by the deterministic check without spending a critic call.
- Graph state is checkpointed, reloadable, and isolated per `thread_id`.
- A vague follow-up returns `action: "clarify"` and leaves the posts untouched.
- `DELETE` clears both the thread index row and the checkpoints.
- A model failure becomes a 500 rather than a stack trace.

## Coverage as it stands

```
Name                           Stmts   Miss Branch BrPart  Cover
configs/database.py               32      0      0      0 100.0%
configs/llms.py                  144      0     46      0 100.0%
configs/logger.py                 30      0      6      0 100.0%
main.py                          133      2     20      2  97.4%
src/agent.py                     135      0     34      0 100.0%
src/graphs/graph.py               47      0      0      0 100.0%
src/models/models.py              21      0      4      0 100.0%
src/node/accept_node.py           20      0      2      0 100.0%
src/node/consistency_node.py      44      0      6      0 100.0%
src/node/manager_node.py          19      0      0      0 100.0%
src/node/self_check_node.py       37      0      8      0 100.0%
src/node/writer_node.py           35      0      2      0 100.0%
src/routes/routing.py             23      0      4      0 100.0%
src/schemas/state.py              31      0      2      0 100.0%
src/store/thread_store.py         79      0     12      0 100.0%
src/utils/prompts.py              20      1      2      1  90.9%
src/utils/trace.py                11      0      2      0 100.0%
TOTAL                            861      3    150      3  99.4%
```

The three uncovered lines are defensive branches that the design already makes unreachable:
two guard against a platform the `RefineIntent` schema's `Literal` type rejects before the
code runs, and one is the `raise` inside the `SHARED_PREFIX` cache-floor guard.
