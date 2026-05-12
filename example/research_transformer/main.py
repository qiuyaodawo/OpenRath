"""CLI for the Research Transformer example (uv-friendly)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

from rath.session.session import Session  # noqa: E402

from _chunk_print import optional_chunk_print  # noqa: E402
from research_transformer.providers import providers_from_env  # noqa: E402
from research_transformer.tools import optional_image_tools  # noqa: E402
from research_transformer.workflow import ResearchTransformerWorkflow  # noqa: E402

DEFAULT_WORKSPACE = (Path(__file__).resolve().parent / ".workspace").resolve()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Research Transformer: multi-stage academic pipeline (OpenRath example). "
            "Default workspace is example/research_transformer/.workspace/"
        ),
    )
    p.add_argument("--research-question", required=True, help="Main research question")
    p.add_argument(
        "--supervisor-notes",
        required=True,
        help="Advisor constraints, taste, or must-haves",
    )
    p.add_argument(
        "--thesis-path",
        required=True,
        type=Path,
        help="Path to a text file with thesis excerpt for the reproduction branch",
    )
    p.add_argument(
        "--ddl-note",
        default="(not specified)",
        help="Deadline / pressure note for the reproduction branch",
    )
    p.add_argument(
        "--layers",
        type=int,
        default=2,
        help="Number of layer repetitions per branch (literature→rewrite and QA→verify)",
    )
    p.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Alias for --layers (if set, overrides --layers)",
    )
    p.add_argument(
        "--workdir",
        default=str(DEFAULT_WORKSPACE),
        help="Sandbox working directory (default: package .workspace/)",
    )
    p.add_argument(
        "--skip-images",
        action="store_true",
        help="Do not register the optional background_image tool",
    )
    p.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable run_session_compress between major stages (may grow context quickly)",
    )
    p.add_argument(
        "--print-chunks",
        action="store_true",
        help="Print one brief line per newly appended chunk (loop, compress, preamble)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    thesis_path: Path = args.thesis_path
    if not thesis_path.is_file():
        print(f"ERROR: thesis path is not a file: {thesis_path}", file=sys.stderr)
        return 2

    layers: int = args.iterations if args.iterations is not None else args.layers
    if layers < 1:
        print("ERROR: --layers (--iterations) must be >= 1", file=sys.stderr)
        return 2

    try:
        thesis_excerpt = thesis_path.read_text(encoding="utf-8", errors="replace")
        prov = providers_from_env()
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    opening = (
        "## Research question\n"
        f"{args.research_question.strip()}\n\n"
        "## Supervisor notes\n"
        f"{args.supervisor_notes.strip()}\n"
    )
    workdir = str(Path(args.workdir).resolve())
    image_tools = optional_image_tools(skip_images=args.skip_images)
    user = Session.from_user_message(opening).to("local", spec=workdir)
    wf = ResearchTransformerWorkflow(
        prov,
        layers=layers,
        thesis_excerpt=thesis_excerpt,
        ddl_note=str(args.ddl_note),
        image_tools=image_tools,
        enable_compress=not args.no_compress,
        chunk_print=optional_chunk_print(args.print_chunks),
    )
    out = wf.forward(user)
    print(out, file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
