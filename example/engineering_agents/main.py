"""CLI for nested engineering_agents workflow."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rath.llm import Provider
from rath.session.session import Session

_EX = Path(__file__).resolve().parent.parent
if str(_EX) not in sys.path:
    sys.path.insert(0, str(_EX))
from _chunk_print import optional_chunk_print  # noqa: E402
from workflows import EngineeringProjectWorkflow  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ClawTeam-style Agentic SE with nested Workflow "
            "(Lead → FeatureSquad[BackendPair] → QA)."
        ),
    )
    parser.add_argument(
        "--goal",
        required=True,
        help='e.g. "Full-stack todo app with auth, DB, React frontend."',
    )
    parser.add_argument(
        "--workdir",
        default=".workspace/",
        help="Local sandbox root.",
    )
    parser.add_argument(
        "--print-chunks",
        action="store_true",
        help="Print one brief line per newly appended chunk (verbose)",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: OPENAI_API_KEY is not set in the process environment.",
            file=sys.stderr,
        )
        sys.exit(2)
    provider = Provider(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or None,
        model=os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None,
    )

    workdir = str(Path(args.workdir).resolve())
    user = Session.from_user_message(args.goal.strip()).to("local", spec=workdir)
    out = EngineeringProjectWorkflow(
        provider=provider,
        chunk_print=optional_chunk_print(args.print_chunks),
    ).forward(user)
    print(out, file=sys.stdout)


if __name__ == "__main__":
    main()
