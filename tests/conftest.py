import os
import subprocess
import sys
from pathlib import Path

import pytest
from media import TOOLS

PUBLIC = Path(__file__).parent / "fixtures" / "public"


def need(tool: str) -> str:
    """Skip when a test tool is missing, unless BLURRY_REQUIRE_TOOLS=1 (CI)."""
    path = TOOLS.get(tool)
    if not path:
        if os.environ.get("BLURRY_REQUIRE_TOOLS") == "1":
            pytest.fail(f"{tool} is required in CI")
        pytest.skip(f"{tool} not installed")
    return path


def run_blurry(*args, env=None, cwd=None) -> subprocess.CompletedProcess:
    """Run the real command in a fresh process (network guard included)."""
    return subprocess.run(
        [sys.executable, "-m", "blurry_opsec", *map(str, args)],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        cwd=cwd,
        timeout=600,
    )


@pytest.fixture
def outdir(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    return d
