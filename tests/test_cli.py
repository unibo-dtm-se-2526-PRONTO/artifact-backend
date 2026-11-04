"""Tests for the command line installed with the package."""

import os
import subprocess
import sys
import tomllib

from django.conf import settings

REPO = settings.BASE_DIR


def run_pronto(*args, cwd, extra_env=None):
    # From another folder, as after `pip install`: the package comes from the repo.
    env = {**os.environ, "PYTHONPATH": str(REPO), **(extra_env or {})}
    env.pop("DEFAULT_FROM_EMAIL", None)
    return subprocess.run(
        [sys.executable, "-m", "pronto", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_package_declares_the_pronto_helpdesk_command():
    with open(REPO / "pyproject.toml", "rb") as f:
        scripts = tomllib.load(f)["tool"]["poetry"]["scripts"]

    assert scripts["pronto-helpdesk"] == "pronto.__main__:main"


def test_python_m_pronto_runs_the_django_commands(tmp_path):
    result = run_pronto("check", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "System check identified no issues" in result.stdout


def test_the_env_file_of_the_current_folder_is_read(tmp_path):
    (tmp_path / ".env").write_text("DEFAULT_FROM_EMAIL=cli@pronto.test\n")

    result = run_pronto(
        "shell",
        "--verbosity",
        "0",
        "-c",
        "from django.conf import settings; print(settings.DEFAULT_FROM_EMAIL)",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cli@pronto.test"
