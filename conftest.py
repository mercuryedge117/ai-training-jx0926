"""Shared pytest fixtures/helpers for the bootcamp test suite.

Every demo degrades to a deterministic mock without API keys (see
course-demos/common/llm.py); tests force that mode so results never depend on
network access, account credentials, or LLM sampling variance.

Session scripts live in hyphenated folders (session-06-structured-extraction)
that can't be `import`ed as normal packages, and several of them rely on
Python's usual "the running script's own directory is on sys.path" behavior
to find sibling modules (e.g. session-05's compare_prompts.py does
`from judge import evaluate`). load_session() replicates both: it loads a
script by file path and puts its directory on sys.path first, the same way
`python that_script.py` would.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
COURSE_DEMOS = ROOT / "course-demos"
SLACK_SIM = ROOT / "slack-simulator"

for p in (COURSE_DEMOS, SLACK_SIM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# Must match common/llm.py's provider list. course-demos/.env is load_dotenv()'d
# at import time, so a key nobody exported can still be sitting in os.environ —
# miss one here and the "tests never touch the network" guarantee quietly dies.
LLM_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY")


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch):
    for key in LLM_KEYS:
        monkeypatch.delenv(key, raising=False)


def load_module(dir_path: Path, module_name: str):
    if str(dir_path) not in sys.path:
        sys.path.insert(0, str(dir_path))
    spec = importlib.util.spec_from_file_location(module_name, dir_path / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_session(session_dir: str, module_name: str):
    """Import course-demos/<session_dir>/<module_name>.py as a fresh module."""
    return load_module(COURSE_DEMOS / session_dir, module_name)
