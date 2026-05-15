"""Budget guardrail exception for :func:`~rath.session.loop.run_session_loop`."""

from __future__ import annotations

__all__ = ["BudgetExceededError"]


class BudgetExceededError(RuntimeError):
    """Raised by user code from ``Provider.on_budget_exceeded`` to abort a loop.

    The session loop itself does not raise this automatically when
    ``budget_total_tokens`` is exceeded - it only invokes the callback (or
    logs a warning if no callback is set). Raising this from the callback is
    the documented way to stop the loop on overrun.
    """
