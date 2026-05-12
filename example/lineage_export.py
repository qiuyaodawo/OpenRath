"""Generate a small session lineage graph and dump it as JSONL.

Run::

    python example/lineage_export.py

No LLM or sandbox required. The script forks and detaches a handful of
sessions inside :func:`lineage_journal_tracking` and writes the resulting
graph to ``lineage_demo.jsonl``. Inspect with ``jq`` for a quick
sanity-check::

    jq '.lineage_operator' lineage_demo.jsonl
"""

from __future__ import annotations

from pathlib import Path

from rath.session import Session
from rath.session.graph import (
    export_journal_jsonl,
    export_jsonl_string,
    lineage_journal_tracking,
)
from rath.session.manager import session_registry


def main() -> None:
    out_path = Path("lineage_demo.jsonl")
    reg = session_registry()

    # ``run_session_loop`` registers sessions automatically. Outside the loop,
    # do it explicitly so the registry-driven exporter can resolve every id in
    # ``journal.visit_order``.
    with lineage_journal_tracking() as journal:
        root = Session.from_user_message("Initial user message.")
        reg.register(root)
        # Two parallel forks off the root.
        plan_branch = root.fork()
        reg.register(plan_branch)
        critique_branch = root.fork()
        reg.register(critique_branch)
        # A detached child off the plan branch (lineage_kind=OP_DETACH).
        reg.register(plan_branch.detach())
        # An extra fork to make the visit_order non-trivial.
        reg.register(critique_branch.fork())

    export_journal_jsonl(journal, out_path)
    print(f"Wrote {len(journal.visit_order)} session rows to {out_path.resolve()}")

    explicit = [root, plan_branch, critique_branch]
    print("---explicit export (3 rows, not registry-driven)---")
    print(export_jsonl_string(explicit), end="")


if __name__ == "__main__":
    main()
