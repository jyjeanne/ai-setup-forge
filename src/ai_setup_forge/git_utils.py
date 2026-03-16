"""Git clone operations via subprocess."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ai_setup_forge.constants import GIT_CLONE_TIMEOUT_SECONDS


class GitError(Exception):
    """Raised when a git operation fails."""


def _get_git_auth_env() -> dict[str, str]:
    """Build environment dict with GitHub token auth if available."""
    import os

    env = os.environ.copy()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        # Try gh auth token
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                token = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if token:
        # Disable interactive prompts
        env["GIT_TERMINAL_PROMPT"] = "0"
        # Rewrite HTTPS URLs to use token auth
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = f"url.https://x-access-token:{token}@github.com/.insteadOf"
        env["GIT_CONFIG_VALUE_0"] = "https://github.com/"

    return env


def shallow_clone(
    url: str,
    ref: str | None = None,
    timeout: int = GIT_CLONE_TIMEOUT_SECONDS,
) -> Path:
    """Clone a git repository shallowly into a temp directory.

    Args:
        url: Git clone URL.
        ref: Optional branch/tag/commit to checkout.
        timeout: Timeout in seconds.

    Returns:
        Path to the cloned directory.

    Raises:
        GitError: If clone fails.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="skills-"))
    clone_dir = tmp_dir / "repo"

    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd.extend(["--branch", ref])
    cmd.extend([url, str(clone_dir)])

    env = _get_git_auth_env()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        cleanup_clone(tmp_dir)
        raise GitError(f"Git clone timed out after {timeout}s: {url}") from None
    except FileNotFoundError:
        cleanup_clone(tmp_dir)
        raise GitError("git is not installed or not in PATH") from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        cleanup_clone(tmp_dir)

        # Detect auth errors
        if "Authentication failed" in stderr or "could not read Username" in stderr:
            raise GitError(
                f"Authentication failed for {url}. Set GITHUB_TOKEN or run 'gh auth login'."
            )
        raise GitError(f"Git clone failed for {url}: {stderr or 'unknown error'}")

    return clone_dir


def cleanup_clone(path: Path) -> None:
    """Remove a cloned temp directory safely.

    Only removes paths under the system temp directory.
    """
    tmp_root = Path(tempfile.gettempdir()).resolve()
    resolved = path.resolve()

    # Safety: only delete if under temp root
    try:
        resolved.relative_to(tmp_root)
    except ValueError:
        return

    if resolved.exists():
        shutil.rmtree(resolved, ignore_errors=True)
        # Also clean parent if it's an empty skills-* dir
        parent = resolved.parent
        if parent.name.startswith("skills-") and parent != tmp_root:
            import contextlib

            with contextlib.suppress(OSError):
                parent.rmdir()  # only succeeds if empty
