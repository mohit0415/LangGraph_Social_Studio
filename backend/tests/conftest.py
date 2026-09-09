import os
import sqlite3
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_DIR = tempfile.mkdtemp(prefix="studio-tests-")
os.environ["STUDIO_DB_PATH"] = str(Path(TEST_DB_DIR) / "test_studio.db")
os.environ.setdefault("LOG_LEVEL", "WARNING")

# Keep the suite off the network. Set before main is imported, so the .env that
# load_dotenv reads later cannot switch tracing back on and make every test wait
# on Langfuse.
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "")

# No AZURE_OPENAI_* here on purpose. The backend no longer reads credentials
# from the environment, so a test that needs them builds an AzureCredentials
# and binds it explicitly — see the `credentials` and `client` fixtures below.
for leftover in (
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_DEPLOYMENT_SIMPLE",
):
    os.environ.pop(leftover, None)


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.fspath)
        if f"{os.sep}unit{os.sep}" in path:
            item.add_marker(pytest.mark.unit)
        elif f"{os.sep}integration{os.sep}" in path:
            item.add_marker(pytest.mark.integration)


BRIEF_TEXT = (
    "CORE MESSAGE: Shipping daily reduces incidents.\n"
    "AUDIENCE: Engineering teams.\n"
    "KEY POINTS:\n"
    "- 1,200 teams studied\n"
    "- 40% fewer incidents\n"
    "- Smaller change sets are the cause\n"
    "ANGLE: It is not better testing."
)


class FakeStudio:
    def __init__(self):
        self.brief = BRIEF_TEXT
        self.drafts = defaultdict(lambda: "A short draft that fits every limit. #Eng")
        self.verdicts = defaultdict(deque)
        self.default_verdict = "OK"
        self.conflicts = []
        self.router_intent = None
        self.calls = []
        self.systems = []

    def set_verdicts(self, platform, verdicts):
        self.verdicts[platform] = deque(verdicts)

    def ask(self, system, user, task="write", routing_text="", **kwargs):
        self.calls.append(task)
        self.systems.append(system)

        if task == "brief":
            return self.brief

        if task == "write":
            platform = self._platform_from(system)
            draft = self.drafts[platform]
            return draft(user) if callable(draft) else draft

        if task == "critique":
            platform = self._platform_from(system)
            queue = self.verdicts[platform]
            return queue.popleft() if queue else self.default_verdict

        return ""

    def ask_structured(self, schema, system, user, task, fallback, **kwargs):
        self.calls.append(task)

        if task == "consistency":
            return schema(conflicts=list(self.conflicts))

        if task == "router":
            if self.router_intent is None:
                return fallback
            return schema(**self.router_intent)

        return fallback

    @staticmethod
    def _platform_from(system):
        for name in ("linkedin", "instagram", "x"):
            if f"a {name} copywriter" in system.lower():
                return name
            if f"fit {name} specifically" in system.lower():
                return name
        return "unknown"


@pytest.fixture
def studio(monkeypatch):
    fake = FakeStudio()
    monkeypatch.setattr("src.agent.ask", fake.ask)
    monkeypatch.setattr("src.agent.ask_structured", fake.ask_structured)
    return fake


@pytest.fixture
def credentials():
    """A credential set shaped like a real one, pointed at nothing."""
    from configs.credentials import AzureCredentials

    return AzureCredentials.build(
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        deployment="test-deployment",
        api_version="2024-02-01",
    )


@pytest.fixture
def bound_credentials(credentials):
    """Credentials bound to the context, as a request would bind them."""
    from configs.credentials import use_credentials
    from configs.llms import clear_model_cache

    clear_model_cache()
    with use_credentials(credentials) as bound:
        yield bound
    clear_model_cache()


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def store(memory_conn):
    from src.store.thread_store import ThreadStore

    return ThreadStore(memory_conn)


@pytest.fixture(scope="session")
def api():
    import main

    return main


@pytest.fixture(scope="session")
def raw_client(api):
    """A client that sends no session header — guarded routes should 401.

    Deliberately not entered as a context manager: the app's lifespan is already
    running for the signed-in `client`, and firing shutdown twice would tear down
    the Langfuse manager underneath it.
    """
    from fastapi.testclient import TestClient

    return TestClient(api.app)


@pytest.fixture(scope="session")
def client(api):
    """A signed-in client.

    The session is created directly on the store rather than through
    /auth/login, so the suite exercises the real dependency without needing an
    Azure endpoint to probe against.
    """
    from fastapi.testclient import TestClient

    from configs.credentials import AzureCredentials
    from src.routes.auth import SESSION_HEADER

    session = api.session_store.create(
        AzureCredentials.build(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="test-deployment",
            api_version="2024-02-01",
        )
    )

    with TestClient(api.app) as test_client:
        test_client.headers[SESSION_HEADER] = session.session_id
        yield test_client

    api.session_store.delete(session.session_id)
