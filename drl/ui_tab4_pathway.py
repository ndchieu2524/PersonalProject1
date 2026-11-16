"""TAB 4 – Lộ trình ĐRL Tối ưu & Kiểm tra Trùng Lịch học (NetworkX Pathway)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config, database, pathway
from . import ui_common as ui
from .ai_engine import explain_route_with_ai


def _route_step_html(idx: int, act: dict) -> str:
    verified = (act.get("relevance_label") == config.LABEL_VERIFIED
                or act.get("verification_status") in (config.VERIFY_ADMIN_APPROVED,
                                                      config.VERIFY_RULE_CITED))
    cls = "sdrs-route-step" if verified else "sdrs-route-step potential"
    tag = ("✅ ĐÃ XÁC MINH – cộng vào điểm Verified" if verified
           else "🟡 TIỀM NĂNG – chỉ cộng vào cột Potential")
    deadline = act.get("registration_deadline")
    deadline_note = ui.fmt_deadline_note(deadline)
    travel = act.get("travel_note") or ""
    demo = ui.demo_tag() if ui.to_int(act.get("is_demo")) else ""
    return f"""<div class="{cls}">
      <div class="ttl">{idx}. {act.get('title')} {demo}</div>
      <div class="meta">⏰ <b>{act.get('start_time')}</b> → <b>{act.get('end_time')}</b>
        &nbsp;·&nbsp; 📍 {act.get('location') or 'chưa rõ địa điểm'}
        ({config.CAMPUS_LABELS.get(act.get('campus'), 'chưa rõ cơ sở')})<br/>
        🎯 Tiêu chí <b>{act.get('criterion_code') or '—'}</b>
        &nbsp;·&nbsp; 🏆 <b>+{float(act.get('expected_score') or 0):g} điểm</b> &nbsp;·&nbsp; {tag}<br/>
        {f'📝 Hạn đăng ký: <b>{deadline}</b> ({deadline_note})<br/>' if deadline else ''}
        {f'🚌 {travel}' if travel else ''}
      </div></div>"""


def render() -> None:
    ui.hero(
        "🧭 Lộ trình ĐRL Tối ưu & Kiểm tra Trùng Lịch học",
        "NetworkX DAG · loại hoạt động trùng giờ học CTĐB · cạnh nối khi kịp di chuyển giữa "
        "Nguyễn Văn Cừ ↔ Linh Trung · tối ưu theo trần điểm từng tiêu chí.",
    )

    profile = database.latest_profile()
    if not profile:
        ui.warn_box("Chưa có hồ sơ sinh viên – hãy nạp dữ liệu [DEMO] hoặc đồng bộ ở Tab 1.")
        return

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.2, 1, 1, 1])
    with ctrl1:
        buffer_minutes = st.slider("Thời gian đệm giữa 2 hoạt động (phút)", 0, 60, 0, 5,
                                   help="Đệm an toàn cộng thêm ngoài thời gian di chuyển.")
        include_past = st.checkbox("Cho phép hoạt động đã kết thúc (chế độ kiểm thử)",
                                   value=False)
    with ctrl2:
        prefer_verified = st.checkbox("Ưu tiên hoạt động đã xác minh", value=True)
    with ctrl3:
        st.metric("Điểm hiện tại", f"{float(profile.get('current_total_score') or 0):g}")
    with ctrl4:
        st.metric("Mục tiêu", f"{float(profile.get('target_score') or 0):g}")

    with st.spinner("Đang dựng đồ thị & tối ưu lộ trình…"):
        result = pathway.compute_optimal_pathway(
            student_id=profile["student_id"], semester=profile["semester"],
            buffer_minutes=buffer_minutes, prefer_verified=prefer_verified,
            include_past=include_past,
        )
    if "error" in result:
        st.error(result["error"])
        return

    route = result["route"]
    verified_gain = route["verified_gain"]
    potential_gain = route["potential_gain"]
    total_gain = route["total_expected_score"]
    current = route["current"]
    target = route["target"]
    projected = min(100.0, current + total_gain)
    projected_verified = min(100.0, current + verified_gain)

    n_demo_route = sum(1 for a in route["activities"] if ui.to_int(a.get("is_demo")))
    if n_demo_route:
        ui.warn_box(
            f"Lộ trình này dựa trên **{n_demo_route}/{len(route['activities'])} hoạt động [DEMO]** "
            "(dữ liệu mẫu do hệ thống tạo, **không phải hoạt động thật của trường**). "
            "Các con số dưới đây chỉ minh hoạ cách hệ thống tính toán. "
            "Hãy thu thập bài đăng thật ở **Tab 2** để có lộ trình thực tế."
        )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tổng điểm lộ trình", f"+{total_gain:g}")
    m2.metric("Trong đó: ĐÃ XÁC MINH", f"+{verified_gain:g}")
    m3.metric("Trong đó: TIỀM NĂNG", f"+{potential_gain:g}",
              help="Không cộng vào điểm chính thức – cần Admin xác minh.")
    m4.metric("Dự phóng (điểm hiện tại + lộ trình)", f"{projected:g}/100",
              delta=f"so mục tiêu {target:g}", delta_color="off")
    remaining = max(0.0, target - projected_verified)
    m5.metric("Còn thiếu so với mục tiêu (tính điểm xác minh)", f"{remaining:g}",
              delta_color="inverse" if remaining > 0 else "normal")

    if projected_verified < target:
        ui.note_box(
            f"Ngay cả khi hoàn thành toàn bộ lộ trình (gồm cả phần **tiềm năng**), sinh viên đạt "
            f"**{projected:g}** điểm, còn thiếu **{max(0.0, target - projected):g}** so với mục tiêu "
            f"**{target:g}**. Hãy bổ sung thêm hoạt động từ Tab 2 hoặc xác minh thêm ở Tab 3."
        )

    st.divider()
    st.subheader("🗺️ Các hoạt động trong lộ trình tối ưu")
    if not route["activities"]:
        ui.warn_box(
            "Không có hoạt động nào đủ điều kiện vào lộ trình. Nguyên nhân thường gặp: thiếu "
            "thời gian/địa điểm/điểm, nhãn chưa đạt POTENTIAL/VERIFIED, hoặc trùng giờ học."
        )
    for idx, act in enumerate(route["activities"], start=1):
        st.markdown(_route_step_html(idx, act), unsafe_allow_html=True)

    # --- Giải thích lộ trình (AI / template nội bộ) ---
    st.subheader("🤖 Giải thích lộ trình (Route Explanation)")
    provider, api_key, model = ui.ai_settings_from_session()
    if st.button("✨ Sinh lời giải thích lộ trình", key="explain_route", type="primary"):
        with st.spinner("Đang sinh giải thích…"):
            text, source = explain_route_with_ai(
                route, profile, ui.criteria_records(),
                provider=provider, api_key=api_key, model=model,
            )
        st.session_state["route_explanation"] = (text, source)
    if st.session_state.get("route_explanation"):
        text, source = st.session_state["route_explanation"]
        st.markdown(text)
        st.caption(f"Nguồn: {source} – chỉ diễn giải các số liệu có thật của lộ trình, không thêm dữ kiện.")

    st.divider()
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("🕸️ Đồ thị hoạt động (NetworkX DiGraph)")
        chosen_ids = [a["id"] for a in route["activities"]]
        try:
            fig = pathway.draw_graph(result["graph"], chosen_ids)
            st.pyplot(fig, width="stretch")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Không vẽ được đồ thị: {exc}")
        st.caption(
            f"Đỉnh: **{result['graph'].number_of_nodes()}** hoạt động hợp lệ · "
            f"Cạnh: **{result['graph'].number_of_edges()}** cạnh tương thích thời gian."
        )

        with st.expander("🔬 So sánh 2 phương pháp tối ưu trên cùng đồ thị"):
            plain = result["plain_longest_path"]
            st.write(f"**(a) `nx.dag_longest_path` (trọng số điểm, KHÔNG xét trần tiêu chí):** "
                     f"tổng {plain['total_expected_score']:g} điểm, {len(plain['nodes'])} hoạt động.")
            if plain["nodes"]:
                st.dataframe(pd.DataFrame(plain["nodes"]).rename(columns={
                    "title": "Hoạt động", "expected_score": "Điểm",
                    "criterion_code": "Tiêu chí", "start_time": "Bắt đầu",
                    "end_time": "Kết thúc", "verified": "Đã xác minh", "id": "ID",
                }), width="stretch", hide_index=True)
            st.write(f"**(b) Quy hoạch động trên DAG tôn trọng trần `max_score` từng tiêu chí "
                     f"(kết quả chính đang hiển thị):** tổng {result['dp']['total_expected_score']:g} điểm.")
            if plain["total_expected_score"] > result["dp"]["total_expected_score"]:
                st.info(
                    "Phương pháp (a) cho tổng điểm danh nghĩa cao hơn nhưng có thể **vượt trần tiêu chí** "
                    "→ không hợp lệ theo quy chế. Đây chính là lý do hệ thống dùng (b) làm kết quả."
                )
            gains = route["gains_by_criterion"]
            if gains:
                st.write("**Điểm theo tiêu chí trong lộ trình:**")
                st.dataframe(pd.DataFrame(
                    [{"Tiêu chí": k, "Điểm trong lộ trình": v,
                      "Dư địa còn lại": route["criterion_missing"].get(k, 0)}
                     for k, v in gains.items()]),
                    width="stretch", hide_index=True)

    with right:
        st.subheader("🚫 Hoạt động bị loại")
        if route["excluded_conflicts"]:
            st.markdown("**Trùng giờ học chính khóa CTĐB:**")
            st.dataframe(pd.DataFrame(route["excluded_conflicts"])[[
                "title", "activity_time", "lesson"]].rename(columns={
                "title": "Hoạt động", "activity_time": "Thời gian", "lesson": "Tiết học bị trùng",
            }), width="stretch", hide_index=True, height=170)
        else:
            st.caption("Không có hoạt động nào trùng giờ học.")

        st.markdown("**Bị loại vì dữ liệu/nhãn:**")
        if route["excluded_missing"]:
            st.dataframe(pd.DataFrame(route["excluded_missing"])[["title", "reason"]].rename(
                columns={"title": "Hoạt động", "reason": "Lý do"},
            ), width="stretch", hide_index=True, height=260)
        else:
            st.caption("Không có.")

    # --- Khám phá ---
    st.divider()
    st.subheader("🔍 Danh sách khám phá – hoạt động chưa đủ điều kiện vào lộ trình")
    discover = database.get_activities()
    discover = discover[discover["relevance_label"].isin(
        [config.LABEL_EVENT_CANDIDATE, config.LABEL_INSUFFICIENT])]
    if discover.empty:
        st.caption("Không có hoạt động nào trong diện khám phá.")
    else:
        st.caption("Các hoạt động này chưa rõ quyền lợi ĐRL hoặc còn thiếu thông tin – "
                   "hãy bổ sung/xác minh ở Tab 3 để đưa vào lộ trình.")
        show = discover[["id", "title", "start_time", "location", "relevance_label",
                         "is_missing_time", "is_missing_location", "is_missing_score"]]
        st.dataframe(show.rename(columns={
            "id": "ID", "title": "Hoạt động", "start_time": "Bắt đầu", "location": "Địa điểm",
            "relevance_label": "Nhãn", "is_missing_time": "Thiếu TG",
            "is_missing_location": "Thiếu ĐĐ", "is_missing_score": "Thiếu Điểm",
        }), width="stretch", hide_index=True, height=220)
