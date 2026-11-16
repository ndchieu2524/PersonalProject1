"""TAB 1 – Dashboard & Đồng bộ Plugin (Portal CTĐB & hcmus.drl.vn)."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from . import config, database, seed_data
from . import ui_common as ui


def _metric_row(profile: dict, verified_gain: float, potential_gain: float) -> None:
    current = float(profile.get("current_total_score") or 0)
    target = float(profile.get("target_score") or 0)
    projected = min(100.0, current + verified_gain)
    gap = max(0.0, target - projected)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("① Điểm hiện tại đã có", f"{current:g}",
              help="Điểm đang có trên hcmus.drl.vn hoặc do sinh viên nhập.")
    c2.metric("② Điểm từ hoạt động ĐÃ XÁC MINH", f"+{verified_gain:g}",
              help="Chỉ cộng từ các hoạt động nhãn VERIFIED_DRL.")
    c3.metric("③ Điểm từ hoạt động TIỀM NĂNG", f"+{potential_gain:g}",
              help="Chỉ để tham khảo (POTENTIAL_DRL) – KHÔNG cộng vào điểm chính thức.")
    c4.metric("④ Mục tiêu học kỳ", f"{target:g}",
              delta=f"còn thiếu {gap:g} điểm" if gap > 0 else "đã đạt mục tiêu",
              delta_color="inverse" if gap > 0 else "normal",
              help="Mục tiêu tính theo (Điểm hiện tại + Điểm đã xác minh).")


def _progress_chart(progress_df: pd.DataFrame) -> None:
    if progress_df.empty:
        return
    chart_df = progress_df[["criterion_code", "name", "current_score", "max_score"]].copy()
    chart_df["Còn thiếu"] = (chart_df["max_score"] - chart_df["current_score"]).clip(lower=0)
    chart_df = chart_df.set_index("criterion_code")[["current_score", "Còn thiếu"]]
    st.caption("Tiến độ từng tiêu chí (chỉ hiển thị khi có điểm chi tiết – KHÔNG chia đều từ tổng điểm)")
    st.bar_chart(chart_df, stack=True, height=260, color=["#2563eb", "#e2e8f0"])


def render() -> None:
    ui.hero(
        "📊 Dashboard & Đồng bộ Plugin HCMUS",
        "Tổng quan Điểm rèn luyện – đồng bộ Thời khóa biểu CTĐB và tiến độ tiêu chí từ "
        "Chrome Extension, hoàn toàn không lưu mật khẩu cổng trường.",
    )

    profile = database.latest_profile()
    if not profile:
        ui.warn_box("Chưa có hồ sơ sinh viên. Hãy dùng **Dữ liệu DEMO** hoặc đồng bộ từ Chrome Extension bên dưới.")
        if st.button("⚡ Khởi tạo dữ liệu [DEMO]", key="dash_seed"):
            seed_data.seed_database()
            st.rerun()
        return

    sid = profile["student_id"]
    semester = profile["semester"]
    progress_df = database.get_criterion_progress(sid, semester)
    schedule_df = database.get_schedule(sid)

    # --- Cảnh báo tổng: dữ liệu đang xem là MẪU hay THẬT? ---
    is_seed_profile = str(profile.get("full_name") or "").startswith(config.DEMO_TAG)
    n_demo_acts = int(database.query_df(
        "SELECT COUNT(*) AS n FROM Activities WHERE is_demo = 1"
    )["n"].iloc[0])
    n_sched_demo = int((schedule_df["is_demo"] == 1).sum()) if "is_demo" in schedule_df else 0

    if is_seed_profile or n_demo_acts:
        bits = []
        if is_seed_profile:
            bits.append(f"hồ sơ **{profile.get('full_name')}**")
        if n_demo_acts:
            bits.append(f"**{int(n_demo_acts)} hoạt động**")
        if n_sched_demo:
            bits.append(f"**{n_sched_demo} buổi** thời khóa biểu")
        if bits:
            ui.warn_box(
                "Ứng dụng đang hiển thị dữ liệu **[DEMO]** (" + ", ".join(bits) + "). "
                "Đây là **dữ liệu mẫu do hệ thống tạo để minh hoạ luồng hoạt động**, "
                "**KHÔNG phải** điểm rèn luyện hay lịch học thật của bạn. "
                "Hãy đồng bộ từ Chrome Extension ở mục bên dưới để thay bằng dữ liệu thật."
            )

    # --- Điểm theo lộ trình đã tính (không tính lại AI) ---
    from . import pathway
    verified_gain = potential_gain = 0.0
    route_activities = []
    try:
        result = pathway.compute_optimal_pathway(student_id=sid, semester=semester)
        if "route" in result:
            verified_gain = result["route"]["verified_gain"]
            potential_gain = result["route"]["potential_gain"]
            route_activities = result["route"]["activities"]
    except Exception:  # noqa: BLE001
        pass

    _metric_row(profile, verified_gain, potential_gain)
    st.caption(ui.profile_summary_oneliner(profile))

    # --- Cảnh báo chỉ nhập tổng điểm ---
    has_detail = bool(profile.get("has_detailed_criteria")) and not progress_df.empty
    if not has_detail:
        ui.warn_box("⚠️ " + config.WARNING_TOTAL_SCORE_ONLY)

    left, right = st.columns([1.15, 1])

    with left:
        st.subheader("🎯 Đặt mục tiêu học kỳ")
        with st.form("target_form", border=True):
            col_a, col_b = st.columns(2)
            new_target = col_a.number_input("Mục tiêu điểm ĐRL (0–100)", min_value=0.0,
                                            max_value=100.0,
                                            value=float(profile.get("target_score") or 90), step=1.0)
            new_semester = col_b.text_input("Học kỳ", value=semester)
            col_c, col_d = st.columns(2)
            new_sid = col_c.text_input("MSSV", value=sid)
            new_name = col_d.text_input("Họ tên", value=profile.get("full_name") or "")
            new_faculty = st.text_input("Khoa", value=profile.get("faculty") or "")
            if st.form_submit_button("💾 Lưu mục tiêu", type="primary"):
                database.upsert_profile({
                    **profile,
                    "student_id": new_sid.strip() or sid,
                    "full_name": new_name,
                    "faculty": new_faculty,
                    "semester": new_semester.strip() or semester,
                    "target_score": new_target,
                    "has_detailed_criteria": int(has_detail),
                })
                database.log_action("UPDATE_TARGET", {"student_id": new_sid, "target": new_target})
                st.success("Đã lưu mục tiêu học kỳ.")
                st.rerun()

        _progress_chart(progress_df)

    with right:
        st.subheader("🔌 Đồng bộ từ Chrome Extension")
        ui.note_box(
            "Mở extension → chọn **Quét trang** khi đang đăng nhập cổng thời khóa biểu và "
            "hcmus.drl.vn → bấm **Xuất hcmus_sync.json** rồi tải lên đây (hoặc dán JSON)."
        )
        sync_mode = st.radio(
            "Cách nạp dữ liệu",
            ["Tải file hcmus_sync.json", "Dán chuỗi JSON", "Gói DEMO mẫu (1 cú nhấp)"],
            horizontal=False, label_visibility="collapsed",
        )
        payload = None
        payload_origin = ""

        if sync_mode == "Tải file hcmus_sync.json":
            uploaded = st.file_uploader("Chọn file JSON", type=["json"], key="sync_upload")
            if uploaded is not None:
                payload_origin = f"file:{uploaded.name}:{uploaded.size}"
                try:
                    payload = json.loads(uploaded.getvalue().decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"File JSON không đọc được: {exc}")
        elif sync_mode == "Dán chuỗi JSON":
            text = st.text_area("Dán nội dung JSON", height=150, key="sync_paste",
                                placeholder='{"sync_source": "HCMUS_CHROME_EXTENSION_V1", ...}')
            if text.strip():
                import hashlib
                payload_origin = "paste:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                payload, parse_errors = ui.parse_sync_json_text(text)
                if parse_errors:
                    st.error("⚠️ " + " · ".join(parse_errors[:3]))
                    payload = None
        else:
            demo_payload = seed_data.demo_sync_payload()
            st.code(json.dumps(demo_payload, ensure_ascii=False, indent=2)[:900] + "\n…",
                    language="json")
            ui.download_json_button(demo_payload, "hcmus_sync_demo.json",
                                    "⬇️ Tải hcmus_sync_demo.json", "dl_demo_sync")
            if st.button("⚡ Áp dụng gói DEMO này", key="apply_demo_sync"):
                payload = demo_payload
                payload_origin = "demo:builtin"

        # --- Kiểm tra & áp dụng: CHỈ chạy khi người dùng bấm nút và chưa áp dụng bản này ---
        applied_origin = st.session_state.get("sync_applied_origin")
        if payload:
            ok, errors = ui.validate_sync_payload(payload)
            if not ok:
                st.error("Gói JSON chưa đúng chuẩn Schema 2:")
                for err in errors[:6]:
                    st.write(f"- {err}")
            else:
                if payload.get("is_demo"):
                    ui.warn_box("Gói đồng bộ này mang nhãn **[DEMO]** – dùng để kiểm thử luồng tích hợp.")
                if applied_origin == payload_origin and payload_origin:
                    st.success("Gói JSON này đã được áp dụng trong phiên hiện tại (không ghi lặp lại).")
                elif st.button("📥 Áp dụng gói JSON vào hồ sơ", type="primary", key="apply_sync_btn"):
                    info = ui.apply_sync_payload(payload)
                    st.session_state["sync_applied_origin"] = payload_origin
                    st.success(
                        f"Đã đồng bộ MSSV {info['student_id']} – {info['semester']}: "
                        f"{info['n_progress']} tiêu chí, {info['n_timetable']} tiết học."
                    )
                    if info.get("kept_previous_score"):
                        ui.warn_box(
                            "Gói JSON **không kèm tổng điểm ĐRL** (thường là gói chỉ chứa thời khóa biểu). "
                            "Hệ thống **giữ nguyên điểm đã đồng bộ trước đó** – không ghi đè bằng 0."
                        )
                    if info.get("kept_previous_progress"):
                        ui.warn_box(
                            "Gói JSON **không kèm bảng tiêu chí chi tiết** → giữ nguyên tiến độ tiêu chí cũ. "
                            "Hãy quét thêm trang **hcmus.drl.vn** để cập nhật điểm từng tiêu chí."
                        )
                    st.rerun()

        st.divider()
        st.subheader("🧰 Dữ liệu DEMO")
        stats = database.dashboard_stats()
        st.caption(
            f"DB hiện có {stats['n_posts']} bài đăng · {stats['n_activities']} hoạt động · "
            f"{stats['n_criteria']} tiêu chí · {stats['n_schedule']} tiết trong TKB."
        )
        cols = st.columns(2)
        if cols[0].button("🔄 Nạp lại (reset) dữ liệu [DEMO]", key="reset_demo"):
            seed_data.seed_database(force=True)
            st.success("Đã reset và nạp lại toàn bộ dữ liệu [DEMO].")
            st.rerun()
        if cols[1].button("🗑️ Xoá dữ liệu DEMO (giữ hồ sơ)", key="clear_demo"):
            with database.transaction() as conn:
                conn.execute("DELETE FROM Activities WHERE is_demo = 1")
                conn.execute("DELETE FROM SourcePosts WHERE is_demo = 1")
            database.log_action("CLEAR_DEMO_ACTIVITIES", {"scope": "is_demo=1"})
            st.success("Đã xoá bài đăng & hoạt động DEMO. Hồ sơ/TKB vẫn giữ nguyên.")
            st.rerun()

    # --- Tiến độ chi tiết + TKB ---
    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📈 Tiến độ từng tiêu chí ĐRL")
        if progress_df.empty:
            ui.warn_box(config.WARNING_TOTAL_SCORE_ONLY)
        else:
            display = progress_df.rename(columns={
                "criterion_code": "Mã", "name": "Tên tiêu chí", "category": "Nhóm",
                "current_score": "Hiện có", "max_score": "Tối đa", "status": "Trạng thái",
                "mandatory": "Bắt buộc",
            }).drop(columns=["Trạng thái"], errors="ignore")
            display["Bắt buộc"] = display["Bắt buộc"].apply(lambda v: "✓" if ui.to_int(v) else "")
            st.dataframe(display, width="stretch", hide_index=True, height=320)
    with col2:
        st.subheader("🗓️ Thời khóa biểu CTĐB đã đồng bộ")
        if schedule_df.empty:
            st.info("Chưa có thời khóa biểu. Hãy đồng bộ từ Chrome Extension.")
        else:
            show = schedule_df[["course_code", "course_name", "day_of_week", "start_time",
                                "end_time", "room", "campus", "is_demo"]].copy()
            show["day_of_week"] = show["day_of_week"].map(
                lambda d: config.WEEKDAY_VI.get(d, d))
            show = show.rename(columns={
                "course_code": "Mã môn", "course_name": "Tên môn", "day_of_week": "Thứ",
                "start_time": "Bắt đầu", "end_time": "Kết thúc", "room": "Phòng",
                "campus": "Cơ sở", "is_demo": "DEMO",
            })
            show["DEMO"] = show["DEMO"].apply(lambda v: "✓" if ui.to_int(v) else "")
            st.dataframe(show, width="stretch", hide_index=True, height=320)

    # --- Lộ trình tóm tắt ---
    st.divider()
    st.subheader("🧭 Tóm tắt lộ trình đề xuất (chi tiết ở Tab 4)")
    if not route_activities:
        st.info("Chưa có hoạt động hợp lệ để lập lộ trình – hãy phân tích thêm bài đăng OSA ở Tab 2.")
    else:
        for idx, act in enumerate(route_activities, start=1):
            verified = act.get("relevance_label") == config.LABEL_VERIFIED
            cls = "sdrs-route-step" if verified else "sdrs-route-step potential"
            tag = "ĐÃ XÁC MINH" if verified else "TIỀM NĂNG"
            st.markdown(
                f"""<div class="{cls}">
                <div class="ttl">{idx}. {act.get('title')}</div>
                <div class="meta">⏰ {act.get('start_time')} → {act.get('end_time')} ·
                📍 {act.get('location') or 'chưa rõ'} ·
                🏆 +{float(act.get('expected_score') or 0):g} điểm ({tag})
                {act.get('criterion_code') or ''}</div></div>""",
                unsafe_allow_html=True,
            )
        st.caption(
            f"Tổng điểm đã xác minh trong lộ trình: **+{verified_gain:g}** · "
            f"Tiềm năng: **+{potential_gain:g}** (chỉ tham khảo)."
        )

    # --- Audit log ---
    with st.expander("🧾 Nhật ký thao tác gần đây (AuditLogs)"):
        logs = database.recent_audit(25)
        if logs.empty:
            st.caption("Chưa có thao tác nào.")
        else:
            st.dataframe(logs.rename(columns={"action": "Hành động", "details": "Chi tiết",
                                              "created_at": "Thời điểm"}),
                         width="stretch", hide_index=True, height=260)
