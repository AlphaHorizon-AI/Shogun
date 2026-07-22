"""Process-local emergency-stop latch and runtime cancellation fan-out."""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("shogun.harakiri_runtime")
_harakiri_active = False


def engage_harakiri_latch() -> None:
    """Synchronously block new process-local output."""
    global _harakiri_active
    _harakiri_active = True


def reset_harakiri_latch() -> None:
    global _harakiri_active
    _harakiri_active = False


def harakiri_latch_active() -> bool:
    return _harakiri_active


async def cancel_active_runtime(reason: str = "HARAKIRI activated") -> dict[str, int]:
    """Stop all registered execution lanes, continuing if one lane fails."""
    engage_harakiri_latch()
    cancelled: dict[str, int] = {"telegram": 0, "stacks": 0, "flows": 0, "approvals": 0}
    telegram_tasks = []
    stack_tasks = []
    flow_tasks = []

    try:
        from shogun.services.telegram_poller import request_cancel_active_telegram_messages

        telegram_tasks = request_cancel_active_telegram_messages(exclude_current=True)
        cancelled["telegram"] = len(telegram_tasks)
    except Exception:
        log.exception("HARAKIRI failed while cancelling Telegram tasks")

    try:
        from shogun.services.stack_orchestrator import request_cancel_all_stack_runs

        stack_tasks = request_cancel_all_stack_runs(exclude_current=True)
        cancelled["stacks"] = len(stack_tasks)
    except Exception:
        log.exception("HARAKIRI failed while cancelling stack tasks")

    try:
        from shogun.engine.flow_engine import request_cancel_all_flow_runs

        flow_tasks = request_cancel_all_flow_runs(exclude_current=True)
        cancelled["flows"] = len(flow_tasks)
    except Exception:
        log.exception("HARAKIRI failed while cancelling flow tasks")

    # All cancellation signals above are issued synchronously before waiting
    # on cleanup, so no execution lane remains live because another lane took
    # time to shut down.
    tasks = telegram_tasks + stack_tasks + flow_tasks
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    try:
        from shogun.services.stack_orchestrator import cancel_all_stack_runs

        await cancel_all_stack_runs(reason)
    except Exception:
        log.exception("HARAKIRI failed while persisting cancelled stack state")

    try:
        from shogun.ronin.core.approval_gate import cancel_all

        cancelled["approvals"] = cancel_all("harakiri")
    except Exception:
        log.exception("HARAKIRI failed while cancelling pending approvals")

    log.critical("HARAKIRI runtime cancellation completed: %s", cancelled)
    return cancelled
