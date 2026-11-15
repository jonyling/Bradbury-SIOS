"""Bradbury SIOS Phase 1 Streamlit: Principal dashboard + practice queues.

Run from the repository root:

    python -m sios ui
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    import streamlit as st

    from sios import PRODUCT_NAME, PRODUCT_TAGLINE, RULE
    from sios.digest import build_digest, compliance_calendar
    from sios.packs import LIVE_PACKS
    from sios.store import open_store
    from sios.synthetic import DISCLAIMER
    from sios.workflow import (
        checklist_progress,
        complete_task,
        human_terminal_action,
        review_package,
        submit_for_review,
    )

    st.set_page_config(page_title=PRODUCT_NAME, layout="wide")
    st.title(PRODUCT_NAME)
    st.caption(f"{PRODUCT_TAGLINE} · Phase 1 MVP")
    st.info(DISCLAIMER)
    st.caption(RULE)

    if "sios_store" not in st.session_state:
        st.session_state.sios_store = open_store()
    store = st.session_state.sios_store

    as_of_default = date(2026, 11, 15)
    with st.sidebar:
        st.header("Session")
        as_of = st.date_input("As of (demo)", value=as_of_default)
        users = {u["user_id"]: u for u in store.users}
        reviewer_id = st.selectbox(
            "Acting reviewer",
            options=list(users),
            format_func=lambda uid: f"{uid} — {users[uid]['display_name']} ({users[uid]['role_key']})",
            index=0,
        )
        page = st.radio(
            "View",
            ["Principal dashboard", "Practice queues", "Engagement checklist", "Approvals"],
        )

    if page == "Principal dashboard":
        digest = build_digest(store, as_of=as_of)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Due ≤7d", len(digest["due_7"]))
        c2.metric("Due ≤14d", len(digest["due_14"]))
        c3.metric("Due ≤30d", len(digest["due_30"]))
        c4.metric("At-risk engagements", len(digest["at_risk_engagements"]))

        st.subheader("Compliance calendar (synthetic)")
        st.dataframe(compliance_calendar(store, as_of=as_of, within_days=45), use_container_width=True)

        st.subheader("At-risk engagements")
        if digest["at_risk_engagements"]:
            st.dataframe(digest["at_risk_engagements"], use_container_width=True)
        else:
            st.write("None on this as-of date.")

        st.subheader("Capacity (open tasks by practice)")
        st.dataframe(digest["capacity"], use_container_width=True)

        st.subheader("Pending ReviewGate packages")
        st.dataframe(digest["pending_review_gates"], use_container_width=True)
        st.caption("News APIs called: no. All figures from synthetic SIOS records.")

    elif page == "Practice queues":
        pack = st.selectbox("Practice pack", list(LIVE_PACKS))
        clients = store.client_map()
        task_rows = []
        for eng in store.live_engagements():
            if eng.pack != pack:
                continue
            client = clients.get(eng.client_id)
            for task in eng.tasks:
                task_rows.append(
                    {
                        "eng_id": eng.eng_id,
                        "client": client.display_name if client else eng.client_id,
                        "task_id": task.task_id,
                        "title": task.title,
                        "status": task.status,
                        "due": task.due,
                        "assignee": task.assignee,
                        "needs_review_gate": task.needs_review_gate,
                        "is_synthetic": True,
                    }
                )
        st.subheader(f"{pack} queue")
        st.dataframe(task_rows, use_container_width=True)
        cal = [
            row
            for row in compliance_calendar(store, as_of=as_of, within_days=60)
            if any(e.eng_id == row.get("eng_id") and e.pack == pack for e in store.engagements)
        ]
        st.subheader("Related compliance")
        st.dataframe(cal, use_container_width=True)

    elif page == "Engagement checklist":
        live_ids = [e.eng_id for e in store.live_engagements()]
        eng_id = st.selectbox("Engagement", live_ids, index=live_ids.index("E-505") if "E-505" in live_ids else 0)
        progress = checklist_progress(store, eng_id)
        eng = store.engagement(eng_id)
        client = store.client_map().get(eng.client_id)
        st.write(
            f"**{eng_id}** · pack `{eng.pack}` · type `{eng.type}` · "
            f"client **{client.display_name if client else eng.client_id}** · "
            f"checklist `{progress.get('checklist_key')}`"
        )
        st.progress(
            (progress["steps_done"] / progress["steps_total"]) if progress["steps_total"] else 0.0,
            text=f"{progress['steps_done']} / {progress['steps_total']} steps done-ish",
        )
        st.dataframe(progress["steps"], use_container_width=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            task_id = st.selectbox("Task", [s["task_id"] for s in progress["steps"]])
            if st.button("Complete task"):
                try:
                    result = complete_task(
                        store, eng_id=eng_id, task_id=task_id, actor_id=reviewer_id, actor_type="HUMAN"
                    )
                    st.success(result)
                except Exception as exc:  # noqa: BLE001 — surface to operator
                    st.error(str(exc))
        with col_b:
            if st.button("Submit for ReviewGate"):
                try:
                    result = submit_for_review(
                        store, eng_id=eng_id, task_id=task_id, actor_id=reviewer_id, actor_type="HUMAN"
                    )
                    st.success(f"Package {result['package_id']} → PENDING_REVIEW")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        with col_c:
            st.caption("Documents (metadata)")
            docs = [d.__dict__ for d in store.documents if d.eng_id == eng_id]
            st.dataframe(docs or [{"note": "No documents on this engagement"}], use_container_width=True)

    else:  # Approvals
        packages = list(store.deliverable_packages.values())
        st.subheader("Deliverable packages")
        st.dataframe(packages or [{"note": "No packages yet — submit a ReviewGate step first"}], use_container_width=True)
        if packages:
            package_id = st.selectbox("Package", [p["package_id"] for p in packages])
            intent = st.selectbox("Reviewer intent", ["APPROVE", "REJECT", "HOLD", "REQUEST_REWORK"])
            if st.button("Run ReviewGate"):
                try:
                    result = review_package(
                        store, package_id=package_id, reviewer_id=reviewer_id, intent=intent
                    )
                    if result.get("persisted"):
                        st.success(f"ReviewGate {result['decision']['review_outcome']} — persisted")
                    else:
                        st.warning(result)
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
            terminal = st.selectbox("Human terminal action", ["LODGED", "SENT", "ISSUED"])
            actor_type = st.selectbox("Actor type", ["HUMAN", "LLM", "AGENT"])
            if st.button("Apply terminal"):
                result = human_terminal_action(
                    store,
                    package_id=package_id,
                    actor_id=reviewer_id,
                    actor_type=actor_type,
                    terminal=terminal,
                )
                if result.get("persisted"):
                    st.success(f"Marked {terminal}")
                else:
                    st.error(f"Denied: {result.get('guard', {}).get('reason_code')}")
        st.subheader("Approval log")
        st.dataframe([a.__dict__ for a in store.approvals], use_container_width=True)


if __name__ == "__main__":
    main()
