from __future__ import annotations

from typing import Any
import os
import shutil
import subprocess

from . import __version__

cmd_env = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ["HOME"],
    "LANG": "C",
    "LC_ALL": "C",
}


def run(cmd: list[str]) -> Any:
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, env=cmd_env)


git_revision_url: str | None
if os.path.exists(".git") and shutil.which("git"):
    try:
        git_revision = run(["git", "rev-parse", "HEAD"]).strip().decode("ascii")
        git_revision_url = f"https://github.com/beeper/linkedin/commit/{git_revision}"
        git_revision = git_revision[:8]
    except (subprocess.SubprocessError, OSError):
        git_revision = "unknown"
        git_revision_url = None

    try:
        git_tag = run(["git", "describe", "--exact-match", "--tags"]).strip().decode("ascii")
    except (subprocess.SubprocessError, OSError):
        git_tag = None
else:
    git_revision = "unknown"
    git_revision_url = None
    git_tag = None

git_tag_url = f"https://github.com/beeper/linkedin/releases/tag/{git_tag}" if git_tag else None

if git_tag and __version__ == git_tag[1:].replace("-", ""):
    version = __version__
    linkified_version = f"[{version}]({git_tag_url})"
else:
    if not __version__.endswith("+dev"):
        __version__ += "+dev"
    version = f"{__version__}.{git_revision}"
    if git_revision_url:
        linkified_version = f"{__version__}.[{git_revision}]({git_revision_url})"
    else:
        linkified_version = version
