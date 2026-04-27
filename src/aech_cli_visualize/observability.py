"""Runtime LLM observability integration."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


def _missing_observability_dependency_message(exc: ModuleNotFoundError) -> str:
    missing_name = str(exc.name or "").strip()
    if missing_name == "aech_llm_observability":
        return (
            "LLM observability requires the aech_llm_observability package from "
            "aech-agent-runtime to be installed in the capability environment."
        )
    if missing_name:
        return (
            "LLM observability dependency import failed; missing "
            f"{missing_name!r}. Rebuild or reinstall the capability environment."
        )
    return "LLM observability dependency import failed. Rebuild or reinstall the capability environment."


def resolve_session_path() -> Path | None:
    """Resolve the Agent Aech runtime session path when this CLI runs in-session."""
    explicit = os.environ.get("AECH_SESSION_PATH")
    if explicit:
        return Path(explicit).expanduser().resolve()

    log_path = os.environ.get("LLM_LOG_PATH")
    if log_path:
        path = Path(log_path).expanduser().resolve()
        return path.parent if path.name == "llm.jsonl" else path

    session_id = os.environ.get("AECH_SESSION_ID")
    if session_id:
        return (Path.home() / ".aech" / "sessions" / session_id).expanduser().resolve()

    return None


def configure_llm_observability() -> Path | None:
    """Configure pydantic-ai instrumentation for the current runtime session."""
    session_path = resolve_session_path()
    if session_path is None:
        return None

    try:
        from aech_llm_observability import init_instrumentation, set_llm_log_path
    except ModuleNotFoundError as exc:
        raise RuntimeError(_missing_observability_dependency_message(exc)) from exc

    session_path.mkdir(parents=True, exist_ok=True)
    init_instrumentation(service_name="aech-cli-visualize")
    set_llm_log_path(session_path / "llm.jsonl")
    return session_path


@contextmanager
def llm_observability_session() -> Iterator[Path | None]:
    """Configure and finalize the standard runtime LLM session artifacts."""
    session_path = configure_llm_observability()
    try:
        yield session_path
    finally:
        finalize_llm_observability(session_path)


def finalize_llm_observability(session_path: Path | None) -> None:
    """Write usage.json for the current session if observability was active."""
    if session_path is None:
        return

    try:
        from aech_llm_observability import generate_usage_summary
    except ModuleNotFoundError as exc:
        raise RuntimeError(_missing_observability_dependency_message(exc)) from exc

    generate_usage_summary(session_path)


def append_llm_log_entry(entry: dict[str, Any]) -> None:
    """Append a custom observability entry to the active runtime llm.jsonl."""
    if resolve_session_path() is None:
        return

    try:
        from aech_llm_observability import get_llm_log_path, get_llm_role
    except ModuleNotFoundError as exc:
        raise RuntimeError(_missing_observability_dependency_message(exc)) from exc

    log_path = get_llm_log_path()
    if log_path is None:
        return

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "span_id": uuid.uuid4().hex[:16],
        "trace_id": uuid.uuid4().hex,
        "operation": "chat",
        "provider": "openai",
        "role": get_llm_role(),
        "status": "OK",
        **entry,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        import json

        handle.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")


@contextmanager
def timed_llm_call() -> Iterator[Callable[[], float]]:
    """Measure a non-pydantic-ai API call in milliseconds."""
    started = time.perf_counter()

    def elapsed_ms() -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    yield elapsed_ms


@contextmanager
def observed_llm_role(role: str) -> Iterator[None]:
    """Label LLM spans with the runtime role expected by harness-manager."""
    try:
        from aech_llm_observability import llm_role
    except ImportError:
        yield
        return

    with llm_role(role):
        yield
