"""CLI entry (real LLM + Alpha Vantage)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rath.session.session import Session

_EX = Path(__file__).resolve().parent.parent
if str(_EX) not in sys.path:
    sys.path.insert(0, str(_EX))
from _chunk_print import optional_chunk_print  # noqa: E402

from _env import require_alpha_vantage_key, require_openai_provider  # noqa: E402
from workflow import TradingAgentsWorkflow  # noqa: E402


def _build_user_message(*, ticker: str, as_of: str) -> str:
    return (
        f"Ticker: {ticker.strip().upper()}\n"
        f"As-of date (context): {as_of.strip()}\n\n"
        "Run the full research workflow. "
        "Analyst: call alpha_vantage_global_quote for this ticker first."
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="OpenRath TradingAgents-style multi-agent run.",
    )
    parser.add_argument("--ticker", required=True, help="US equity symbol, e.g. NVDA")
    parser.add_argument(
        "--as-of",
        default="",
        help="Analysis date label (context only), e.g. 2026-01-15",
    )
    parser.add_argument(
        "--workdir",
        default=".workspace/",
        help="Local sandbox working directory (absolute after resolve).",
    )
    parser.add_argument(
        "--print-chunks",
        action="store_true",
        help="Print one brief line per newly appended chunk (verbose)",
    )
    args = parser.parse_args(argv)

    prov = require_openai_provider()
    require_alpha_vantage_key()

    as_of = args.as_of.strip() or "(not specified)"
    workdir = str(Path(args.workdir).resolve())

    workflow = TradingAgentsWorkflow(
        provider=prov,
        chunk_print=optional_chunk_print(args.print_chunks),
    )
    msg = _build_user_message(ticker=args.ticker, as_of=as_of)
    user = Session.from_user_message(msg).to("local", spec=workdir)
    out = workflow.forward(user)

    print(out, file=sys.stdout)


if __name__ == "__main__":
    main()
