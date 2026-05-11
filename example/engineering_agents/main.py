"""CLI for nested engineering_agents workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rath.llm import load_rath_llm_settings
from rath.session.session import Session

from workflows import EngineeringProjectWorkflow


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
    args = parser.parse_args(argv)

    try:
        settings = load_rath_llm_settings()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    model = settings.default_model or "glm-5.1"

    workdir = str(Path(args.workdir).resolve())
    user = Session.from_user_message(args.goal.strip()).to("local", spec=workdir)
    out = EngineeringProjectWorkflow(model=model).forward(user)
    print(out, file=sys.stdout)


if __name__ == "__main__":
    main()
