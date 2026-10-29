"""tools/check-publish.sh: what must not reach the public history is caught, quietly."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "check-publish.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash"
)

SECRET = "zxq-private-token"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("hello\n")
    _commit(path, "base")
    return path


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ["PATH"],
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "1+test@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "1+test@users.noreply.github.com",
    }
    env.update(extra)
    return env


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, env=_env(repo.parent))


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-gpg-sign", "-m", message)


def _check(repo: Path, range_: str = "main..HEAD", **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), range_],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_env(repo.parent, **env),
    )


def _branch(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "work")


def test_clean_range_passes(repo: Path) -> None:
    _branch(repo)
    (repo / ".env.example").write_text("FIREFLY_URL=\n")
    _commit(repo, "docs: example env")
    result = _check(repo, PUBLISH_DENY_PATTERNS=SECRET)
    assert result.returncode == 0, result.stderr


def test_forbidden_path_is_caught_even_if_removed_later(repo: Path) -> None:
    _branch(repo)
    (repo / ".mailmap").write_text("x\n")
    _commit(repo, "add")
    (repo / ".mailmap").unlink()
    _commit(repo, "remove")
    result = _check(repo)
    assert result.returncode == 1
    assert ".mailmap" in result.stderr


@pytest.mark.parametrize("name", ["notes.bundle", "KIMI-BRIEF.md", ".remember/now.md"])
def test_other_forbidden_paths(repo: Path, name: str) -> None:
    _branch(repo)
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n")
    _commit(repo, "add")
    assert _check(repo).returncode == 1


def test_rename_to_a_forbidden_path_is_caught(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "work")
    (repo / "plain.txt").write_text("some content that is long enough to be a rename\n" * 5)
    _commit(repo, "add")
    _git(repo, "checkout", "-q", "-b", "later")
    _git(repo, "mv", "plain.txt", ".mailmap")
    _commit(repo, "rename")
    result = _check(repo, "work..later")
    assert result.returncode == 1
    assert ".mailmap" in result.stderr


def test_personal_string_in_an_added_line_is_caught_without_echoing_it(repo: Path) -> None:
    _branch(repo)
    (repo / "doc.md").write_text(f"contact {SECRET}\n")
    _commit(repo, "docs: contact")
    result = _check(repo, PUBLISH_DENY_PATTERNS="# comment\n\nZXQ-PRIVATE-.*")
    assert result.returncode == 1
    assert "doc.md" in result.stderr
    assert "zxq" not in result.stderr.lower()


def test_personal_string_in_the_message_or_identity_is_caught(repo: Path) -> None:
    _branch(repo)
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-gpg-sign", "-m", f"fix: {SECRET}")
    result = _check(repo, PUBLISH_DENY_PATTERNS=SECRET)
    assert result.returncode == 1
    assert "identity or message" in result.stderr
    assert "zxq" not in result.stderr.lower()


def test_a_message_line_that_looks_like_a_delimiter_does_not_hide_the_rest(repo: Path) -> None:
    _branch(repo)
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-gpg-sign", "-m", f"chore\n\n@@@END\n{SECRET}")
    result = _check(repo, PUBLISH_DENY_PATTERNS=SECRET)
    assert result.returncode == 1
    assert "identity or message" in result.stderr


def test_an_added_line_in_an_oddly_named_file_is_caught(repo: Path) -> None:
    _branch(repo)
    (repo / 'café "x".txt').write_text(f"{SECRET}\n")
    _commit(repo, "add")
    result = _check(repo, PUBLISH_DENY_PATTERNS=SECRET)
    assert result.returncode == 1
    assert "zxq" not in result.stderr.lower()


def test_an_invalid_pattern_fails_the_check_without_quoting_it(repo: Path) -> None:
    _branch(repo)
    (repo / "a.txt").write_text("a\n")
    _commit(repo, "chore: a")
    result = _check(repo, PUBLISH_DENY_PATTERNS=f"{SECRET}(")
    assert result.returncode == 1
    assert "invalid" in result.stderr
    assert "zxq" not in result.stderr.lower()


def test_a_bad_range_fails_instead_of_passing(repo: Path) -> None:
    result = _check(repo, "nope..HEAD", PUBLISH_DENY_PATTERNS=SECRET)
    assert result.returncode != 0


def test_pattern_file_is_read_and_a_blank_line_does_not_match_everything(
    repo: Path, tmp_path: Path
) -> None:
    _branch(repo)
    (repo / "a.txt").write_text("nothing special\n")
    _commit(repo, "chore: a")
    patterns = tmp_path / "patterns"
    patterns.write_text(f"\n   \n# only comments and blanks\n{SECRET}\n")
    assert _check(repo, PUBLISH_DENY_FILE=str(patterns)).returncode == 0


def test_missing_patterns_are_a_notice_locally_and_a_failure_when_required(repo: Path) -> None:
    _branch(repo)
    (repo / "a.txt").write_text("a\n")
    _commit(repo, "chore: a")
    local = _check(repo)
    assert local.returncode == 0
    assert "not checked" in local.stderr
    required = _check(repo, PUBLISH_REQUIRE_PATTERNS="true")
    assert required.returncode == 1
