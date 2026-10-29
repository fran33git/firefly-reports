"""tools/check-identity.sh: the email is what must stay private, whoever the author is."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "check-identity.sh"
NOREPLY = "1+someone@users.noreply.github.com"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash"
)


def _run(cwd: Path, *args: str, **identity: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(cwd),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        **identity,
    }
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)


def _commit(repo: Path, author: tuple[str, str], committer: tuple[str, str]) -> str:
    identity = {
        "GIT_AUTHOR_NAME": author[0],
        "GIT_AUTHOR_EMAIL": author[1],
        "GIT_COMMITTER_NAME": committer[0],
        "GIT_COMMITTER_EMAIL": committer[1],
    }
    _run(repo, "git", "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "c", **identity)
    return _run(repo, "git", "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    assert _run(path, "git", "init", "-q", "-b", "main").returncode == 0
    return path


def _check(repo: Path, base: str) -> subprocess.CompletedProcess[str]:
    return _run(repo, "bash", str(SCRIPT), f"{base}..HEAD")


def test_any_name_is_fine_with_a_noreply_address(repo: Path) -> None:
    base = _commit(repo, ("Base", NOREPLY), ("Base", NOREPLY))
    _commit(repo, ("Any Name", NOREPLY), ("Another Name", NOREPLY))
    assert _check(repo, base).returncode == 0


def test_github_web_flow_committer_is_accepted(repo: Path) -> None:
    base = _commit(repo, ("Base", NOREPLY), ("Base", NOREPLY))
    _commit(repo, ("Any Name", NOREPLY), ("GitHub", "noreply@github.com"))
    assert _check(repo, base).returncode == 0


@pytest.mark.parametrize("role", ["author", "committer"])
def test_a_personal_address_is_refused(repo: Path, role: str) -> None:
    base = _commit(repo, ("Base", NOREPLY), ("Base", NOREPLY))
    personal = ("Someone", "someone@example.org")
    _commit(
        repo,
        personal if role == "author" else ("Someone", NOREPLY),
        personal if role == "committer" else ("Someone", NOREPLY),
    )
    result = _check(repo, base)
    assert result.returncode == 1
    assert role in result.stderr
