"""Cross-platform subprocess policy for Tool Shed background execution.

Interactive commands retain platform defaults. Dashboard workers and safety passes
opt into the context below so nested console children stay windowless on Windows.
"""

from __future__ import annotations

import contextlib
import contextvars
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator


_WINDOWLESS = contextvars.ContextVar("tool_shed_windowless_subprocesses", default=False)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


@contextlib.contextmanager
def windowless_subprocesses() -> Iterator[None]:
    """Make nested subprocess calls windowless for this execution context."""

    token = _WINDOWLESS.set(True)
    try:
        yield
    finally:
        _WINDOWLESS.reset(token)


def _kwargs(kwargs: dict[str, Any], *, windowless: bool | None) -> dict[str, Any]:
    configured = dict(kwargs)
    enabled = _WINDOWLESS.get() if windowless is None else windowless
    if enabled and platform.system().lower() == "windows":
        configured["creationflags"] = int(configured.get("creationflags", 0)) | CREATE_NO_WINDOW
    return configured


def run(
    *popenargs: Any, windowless: bool | None = None, **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    """Run a child with the active background-window policy."""

    return subprocess.run(*popenargs, **_kwargs(kwargs, windowless=windowless))


def popen(
    *popenargs: Any, windowless: bool | None = None, **kwargs: Any
) -> subprocess.Popen[Any]:
    """Start a child with the active background-window policy."""

    return subprocess.Popen(*popenargs, **_kwargs(kwargs, windowless=windowless))


def background_python_executable(executable: str | Path | None = None) -> str:
    """Prefer pythonw for persistent Windows workers when it is installed."""

    selected = Path(executable or sys.executable).resolve()
    if platform.system().lower() == "windows":
        windowless = selected.with_name("pythonw.exe")
        if windowless.is_file():
            selected = windowless
    return str(selected)
