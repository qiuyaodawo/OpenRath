"""02 · Session lineage — fork, detach, and the session graph (no LLM key).

A `Session` is OpenRath's tensor; `fork()` / `detach()` mirror torch's
`clone()` / `detach()`. A fork records its parent; a detach starts a fresh
lineage root. With many sessions, those parent links form a graph you can
traverse and export. This script needs **no API key**.

Run:
    python example/02_session_lineage.py
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from rath.session import Session
from rath.session.graph import (
    ancestors_bfs,
    edge_pairs,
    export_journal_jsonl,
    lineage_journal_tracking,
)
from rath.session.manager import session_registry


def show_fork_vs_detach() -> None:
    root = Session.from_user_message("Plan a small project.")
    forked = root.fork()  # clone() analogue — keeps the parent link
    detached = root.detach()  # detach() analogue — new lineage root

    print(f"root.id          = {root.id}")
    print(
        f"forked.parents   = {forked.parent_session_ids}  "
        f"kind={forked.lineage_kind.name}"
    )
    print(
        f"detached.parents = {detached.parent_session_ids}  "
        f"kind={detached.lineage_kind.name}"
    )


def build_and_export_graph() -> None:
    """Fork/detach a handful of sessions, then traverse and export the graph.

    ``run_session_loop`` registers sessions automatically; outside the loop we
    register them by hand so the journal exporter can resolve every id.
    """
    reg = session_registry()
    with lineage_journal_tracking() as journal:
        root = Session.from_user_message("Initial user message.")
        reg.register(root)
        plan = root.fork()
        reg.register(plan)
        critique = root.fork()
        reg.register(critique)
        reg.register(plan.detach())
        leaf = critique.fork()
        reg.register(leaf)

    by_id: dict[UUID, Session] = {s.id: s for s in (root, plan, critique, leaf)}
    print("\nedges (parent -> child):")
    for parent, child in edge_pairs(by_id):
        print(f"  {parent} -> {child}")
    print(f"\nancestors of leaf (nearest first): {ancestors_bfs(by_id, leaf.id)}")

    out_path = Path("lineage_demo.jsonl")
    export_journal_jsonl(journal, out_path)
    print(f"\nwrote {len(journal.visit_order)} session rows to {out_path.resolve()}")


def main() -> None:
    show_fork_vs_detach()
    build_and_export_graph()


if __name__ == "__main__":
    main()
