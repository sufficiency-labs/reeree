"""Shared test fixtures for reeree."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from reeree.config import Config
from reeree.plan import Plan, Step


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary git project directory with sample files."""
    # Init git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create sample files
    (tmp_path / "main.py").write_text(
        'def hello():\n    print("hello world")\n\nif __name__ == "__main__":\n    hello()\n'
    )
    (tmp_path / "utils.py").write_text(
        'def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n'
    )
    (tmp_path / "README.md").write_text("# Test Project\nA test project for reeree.\n")

    # Initial commit
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, capture_output=True)

    return tmp_path


@pytest.fixture
def config():
    """Create a test config (uses together.ai if key available, otherwise skips LLM tests)."""
    return Config()


@pytest.fixture
def config_with_key():
    """Config that definitely has an API key. Skip if not available."""
    c = Config()
    if not c.api_key:
        pytest.skip("No together.ai API key available")
    return c


@pytest.fixture
def sample_plan():
    """A sample plan with various step states."""
    return Plan(
        intent="add error handling to the project",
        steps=[
            Step(description="Add try/except to main()", status="done", files=["main.py"], commit_hash="abc1234"),
            Step(description="Add input validation to utils.py", status="active", files=["utils.py"], daemon_id=1),
            Step(description="Add logging throughout", status="pending", files=["main.py", "utils.py"]),
            Step(description="Write tests for error cases", status="pending"),
            Step(description="Update README with error handling docs", status="blocked"),
        ],
    )


@pytest.fixture
def simple_plan():
    """A minimal plan with one pending step."""
    return Plan(
        intent="fix the bug",
        steps=[
            Step(description="Fix the off-by-one error in utils.py", files=["utils.py"]),
        ],
    )
