"""Thành phần giao diện dùng chung cho 6 tab Streamlit."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

from . import config, database, nlp_engine, seed_data

# ---------------------------------------------------------------------------
# CSS & thương hiệu
# ---------------------------------------------------------------------------
BRAND_CSS = """
<style>
    .main .block-container {padding-top: 1.2rem; max-width: 1280px;}
    .sdrs-hero {
        background: linear-gradient(120deg, #0b2a5b 0%, #1445a0 55%, #1f6feb 100%);
        color: white; padding: 1.15rem 1.4rem; border-radius: 14px; margin-bottom: 1rem;
        box-shadow: 0 6px 18px rgba(11,42,91,.18);
    }
    .sdrs-hero h1 {font-size: 1.42rem; margin: 0 0 .25rem 0; color: white;}
    .sdrs-hero p {margin: 0; opacity: .92; font-size: .92rem;}
    .sdrs-badge {
        display: inline-block; padding: .12rem .55rem; border-radius: 999px;
        font-size: .74rem; font-weight: 600; white-space: nowrap;
    }
    .bd-verified {background:#dcfce7; color:#166534;}
    .bd-potential {background:#fef3c7; color:#92400e;}
    .bd-candidate {background:#dbeafe; color:#1e40af;}
    .bd-insufficient {background:#fee2e2; color:#991b1b;}
    .bd-notrel {background:#e5e7eb; color:#374151;}
    .sdrs-card {
        border: 1px solid #e2e8f0; border-radius: 12px; padding: .85rem 1rem;
        background: #fff; margin-bottom: .7rem;
    }
    .sdrs-card h4 {margin: 0 0 .35rem 0; font-size: .98rem;}
    .sdrs-note {
        background:#eff6ff; border-left:4px solid #1d4ed8; padding:.65rem .9rem;
        border-radius:8px; font-size:.86rem; margin:.35rem 0 .8rem 0;
    }
    .sdrs-warn {
        background:#fef2f2; border-left:4px solid #dc2626; padding:.65rem .9rem;
        border-radius:8px; font-size:.88rem; margin:.35rem 0 .8rem 0;
    }
    .sdrs-demo-tag {
        background:#111827; color:#fde68a; font-size:.68rem; padding:.08rem .45rem;
        border-radius:6px; font-weight:700; letter-spacing:.02em;
    }
    .sdrs-route-step {
        border-left: 5px solid #16a34a; background:#f0fdf4; border-radius: 8px;
        padding: .6rem .85rem; margin-bottom: .5rem;
    }
    .sdrs-route-step.potential {border-left-color:#d97706; background:#fffbeb;}
    .sdrs-route-step .ttl {font-weight: 650; font-size: .95rem;}
    .sdrs-route-step .meta {font-size: .83rem; color:#475569; margin-top:.15rem;}
    div[data-testid="stMetricValue"] {font-size: 1.35rem;}
    .sdrs-footer {color:#64748b; font-size:.78rem; margin-top:1.5rem;
        border-top:1px solid #e2e8f0; padding-top:.6rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(BRAND_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="sdrs-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def label_badge(label: str) -> str:
    cls = {
        config.LABEL_VERIFIED: "bd-verified",
        config.LABEL_POTENTIAL: "bd-potential",
        config.LABEL_EVENT_CANDIDATE: "bd-candidate",
        config.LABEL_INSUFFICIENT: "bd-insufficient",
        config.LABEL_NOT_RELEVANT: "bd-notrel",
    }.get(label, "bd-notrel")
    icon = config.LABEL_ICONS.get(label, "")
    return f'<span class="sdrs-badge {cls}">{icon} {label}</span>'


def demo_tag() -> str:
    return '<span class="sdrs-demo-tag">[DEMO]</span>'


def note_box(text: str) -> None:
    st.markdown(f'<div class="sdrs-note">{text}</div>', unsafe_allow_html=True)


def warn_box(text: str) -> None:
    st.markdown(f'<div class="sdrs-warn">{text}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        f'<div class="sdrs-footer">Smart DRL Assistant HCMUS – MVP. {config.DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Định dạng bảng hiển thị
# ---------------------------------------------------------------------------
def to_int(value, default: int = 0) -> int:
    """Ép int an toàn: None / NaN / '' / chuỗi lạ → default (Pandas trả NaN cho cột rỗng)."""
    try:
        if value is None:
            return default
        if isinstance(value, float) and value != value:  # NaN
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value, default: float = 0.0) -> float:
    """Ép float an toàn tương tự ``to_int``."""
    try:
        if value is None:
            return default
        result = float(value)
        return default if result != result else result
    except (TypeError, ValueError):
        return default


ACTIVITY_DISPLAY_COLUMNS = {
    "id": "ID",
    "title": "Hoạt động",
    "organizer": "Đơn vị tổ chức",
    "location": "Địa điểm",
    "campus": "Cơ sở",
    "start_time": "Bắt đầu",
    "end_time": "Kết thúc",
    "registration_deadline": "Hạn đăng ký",
    "expected_score": "Điểm ĐRL",
    "criterion_code": "Tiêu chí",
    "relevance_label": "Nhãn",
    "verification_status": "Xác minh",
    "is_missing_time": "Thiếu TG",
    "is_missing_location": "Thiếu ĐĐ",
    "is_missing_content": "Thiếu ND",
    "is_missing_score": "Thiếu Điểm",
    "is_demo": "DEMO",
}

FLAG_TO_COLUMN = {
    "is_missing_time": "start_time",
    "is_missing_location": "location",
    "is_missing_content": "title",
    "is_missing_score": "expected_score",
}


def activities_to_display_df(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ACTIVITY_DISPLAY_COLUMNS if c in df.columns]
    out = df[cols].copy()
    out = out.rename(columns=ACTIVITY_DISPLAY_COLUMNS)
    if "DEMO" in out.columns:
        out["DEMO"] = out["DEMO"].apply(lambda v: "✓" if to_int(v) == 1 else "")
    for col in ("Thiếu TG", "Thiếu ĐĐ", "Thiếu ND", "Thiếu Điểm"):
        if col in out.columns:
            out[col] = out[col].apply(lambda v: "⚠" if to_int(v) == 1 else "")
    return out


def style_activity_table(src_df: pd.DataFrame, display_df: pd.DataFrame):
    """Tô đỏ các ô thiếu dữ liệu, tô xanh nhãn VERIFIED, cam POTENTIAL."""
    flag_by_original = {
        src.get("id"): src for src in src_df.fillna("").to_dict("records")
    }
    ids = list(src_df["id"]) if "id" in src_df.columns else []
    style_df = display_df.copy()

    def row_style(row):
        row_id = None
        try:
            row_id = ids[row.name]
        except Exception:  # noqa: BLE001
            pass
        record = flag_by_original.get(row_id, {})
        styles = []
        for col in style_df.columns:
            css = ""
            if col == ACTIVITY_DISPLAY_COLUMNS.get(FLAG_TO_COLUMN["is_missing_time"]) and \
                    to_int(record.get("is_missing_time")) == 1:
                css = "background-color:#fee2e2;color:#991b1b;font-weight:600"
            elif col == ACTIVITY_DISPLAY_COLUMNS.get(FLAG_TO_COLUMN["is_missing_location"]) and \
                    to_int(record.get("is_missing_location")) == 1:
                css = "background-color:#fee2e2;color:#991b1b;font-weight:600"
            elif col == ACTIVITY_DISPLAY_COLUMNS.get(FLAG_TO_COLUMN["is_missing_content"]) and \
                    to_int(record.get("is_missing_content")) == 1:
                css = "background-color:#fee2e2;color:#991b1b;font-weight:600"
            elif col == ACTIVITY_DISPLAY_COLUMNS.get(FLAG_TO_COLUMN["is_missing_score"]) and \
                    to_int(record.get("is_missing_score")) == 1:
                css = "background-color:#fee2e2;color:#991b1b;font-weight:600"
            elif col == "Nhãn":
                label = record.get("relevance_label")
                if label == config.LABEL_VERIFIED:
                    css = "background-color:#dcfce7;color:#166534;font-weight:600"
                elif label == config.LABEL_POTENTIAL:
                    css = "background-color:#fef3c7;color:#92400e"
                elif label == config.LABEL_INSUFFICIENT:
                    css = "background-color:#fee2e2;color:#991b1b"
                elif label == config.LABEL_NOT_RELEVANT:
                    css = "color:#6b7280"
            styles.append(css)
        return styles

    return style_df.style.apply(row_style, axis=1)


def show_activities_table(df: pd.DataFrame, height: int = 430, key: str = "tbl") -> None:
    if df.empty:
        st.info("Không có dữ liệu phù hợp bộ lọc.")
        return
    display = activities_to_display_df(df)
    st.dataframe(
        style_activity_table(df.reset_index(drop=True), display),
        width="stretch", height=height, hide_index=True, key=key,
    )


# ---------------------------------------------------------------------------
# Đồng bộ gói JSON từ Chrome Extension
# ---------------------------------------------------------------------------
REQUIRED_SYNC_KEYS = ["sync_source", "student_profile", "drl_progress", "timetable"]


def validate_sync_payload(payload: dict) -> tuple[bool, list[str]]:
    """Kiểm tra cấu trúc gói JSON Schema 2 trước khi ghi vào DB."""
    errors: list[str] = []
    for key in REQUIRED_SYNC_KEYS:
        if key not in payload:
            errors.append(f"Thiếu khoá bắt buộc: '{key}'")
    profile = payload.get("student_profile") or {}
    if not str(profile.get("student_id") or "").strip():
        errors.append("student_profile.student_id không được rỗng")
    if not str(profile.get("semester") or "").strip():
        errors.append("student_profile.semester không được rỗng")
    try:
        float(profile.get("current_total_score") or 0)
    except (TypeError, ValueError):
        errors.append("student_profile.current_total_score phải là số")
    for idx, row in enumerate(payload.get("drl_progress") or []):
        if not row.get("criterion_code"):
            errors.append(f"drl_progress[{idx}] thiếu criterion_code")
    for idx, row in enumerate(payload.get("timetable") or []):
        for key in ("course_code", "day_of_week", "start_time", "end_time"):
            if not row.get(key):
                errors.append(f"timetable[{idx}] thiếu '{key}'")
    return (len(errors) == 0), errors


def apply_sync_payload(payload: dict, db_path=None) -> dict:
    """Ghi gói đồng bộ vào SQLite: tiêu chí → hồ sơ → tiến độ → thời khóa biểu."""
    profile_in = payload["student_profile"]
    student_id = str(profile_in["student_id"]).strip()
    semester = str(profile_in["semester"]).strip()
    is_demo = bool(payload.get("is_demo"))
    progress_rows = payload.get("drl_progress") or []

    # 1. Cập nhật danh mục tiêu chí (nếu gói mang theo tên/max_score)
    for row in progress_rows:
        code = row.get("criterion_code")
        if not code:
            continue
        existing = database.get_criteria_dict(db_path).get(code)
        database.upsert_criterion({
            "code": code,
            "name": row.get("name") or (existing or {}).get("name") or code,
            "category": (existing or {}).get("category", ""),
            "max_score": float(row.get("max_score") or (existing or {}).get("max_score") or 0),
            "mandatory": bool(row.get("mandatory", (existing or {}).get("mandatory", 0))),
            "evidence_required": (existing or {}).get("evidence_required", ""),
            "rule_reference": (existing or {}).get("rule_reference", ""),
            "is_demo": (existing or {}).get("is_demo", int(is_demo)),
        }, db_path)

    # 2. Hồ sơ sinh viên (giữ nguyên target_score cũ nếu có)
    old_profile = database.get_profile(student_id, semester, db_path)
    target = float(old_profile.get("target_score") or 0) or 90.0

    # Quan trọng: gói chỉ có THỜI KHÓA BIỂU (chưa quét trang DRL) không được phép
    # ghi đè điểm rèn luyện đã đồng bộ trước đó thành 0.
    raw_total = profile_in.get("current_total_score")
    has_score = raw_total is not None and str(raw_total).strip() != ""
    if has_score:
        try:
            new_total = float(raw_total)
        except (TypeError, ValueError):
            new_total = None
    else:
        new_total = None
    if new_total is None:
        new_total = float(old_profile.get("current_total_score") or 0)
        kept_old_score = bool(old_profile.get("current_total_score"))
    else:
        kept_old_score = False

    incoming_score_type = profile_in.get("score_type") or ""
    if new_total and not kept_old_score and incoming_score_type:
        score_type = incoming_score_type
    else:
        score_type = old_profile.get("score_type") or config.SCORE_TYPE_OFFICIAL

    database.upsert_profile({
        "student_id": student_id,
        "full_name": profile_in.get("full_name") or old_profile.get("full_name", ""),
        "faculty": profile_in.get("faculty") or old_profile.get("faculty", ""),
        "semester": semester,
        "current_total_score": new_total,
        "score_type": score_type,
        "target_score": target,
        "has_detailed_criteria": bool(progress_rows) or bool(old_profile.get("has_detailed_criteria")),
    }, db_path)

    # 3. Tiến độ từng tiêu chí – chỉ thay thế khi gói mang theo tiêu chí.
    #    Nếu gói rỗng (chỉ TKB), giữ nguyên tiến độ đã lưu để không mất dữ liệu.
    if progress_rows:
        database.replace_criterion_progress(student_id, semester, progress_rows, db_path)
        n_progress = len(progress_rows)
    else:
        n_progress = len(database.get_criterion_progress(student_id, semester, db_path))

    # 4. Thời khóa biểu
    timetable_rows = [dict(r) for r in (payload.get("timetable") or [])]
    if timetable_rows:
        database.replace_schedule(student_id, semester, timetable_rows,
                                  synced_from=payload.get("sync_source", config.SYNC_SOURCE_TAG),
                                  is_demo=is_demo, db_path=db_path)

    database.log_action("SYNC_FROM_EXTENSION", {
        "student_id": student_id,
        "semester": semester,
        "sync_source": payload.get("sync_source"),
        "synced_at": payload.get("synced_at"),
        "n_progress": len(progress_rows),
        "n_timetable": len(timetable_rows),
        "kept_previous_score": kept_old_score,
        "is_demo": is_demo,
    }, db_path)
    return {
        "student_id": student_id,
        "semester": semester,
        "n_progress": n_progress,
        "n_timetable": len(timetable_rows),
        "kept_previous_score": kept_old_score,
        "kept_previous_progress": not bool(progress_rows),
    }


def parse_sync_json_text(text: str) -> tuple[Optional[dict], list[str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"JSON không hợp lệ: {exc}"]
    if not isinstance(payload, dict):
        return None, ["Nội dung JSON phải là một object {...}"]
    ok, errors = validate_sync_payload(payload)
    return (payload if ok else None), errors


# ---------------------------------------------------------------------------
# Hiển thị & tải file
# ---------------------------------------------------------------------------
def download_json_button(data: dict | list, filename: str, label: str, key: str) -> None:
    st.download_button(
        label,
        data=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=filename,
        mime="application/json",
        key=key,
    )


def download_csv_button(df: pd.DataFrame, filename: str, label: str, key: str) -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def parse_dt(value: Optional[str]):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def fmt_deadline_note(value: Optional[str]) -> str:
    dt = parse_dt(value)
    if not dt:
        return ""
    delta = (dt - datetime.now()).days
    if delta < 0:
        return "⛔ Hạn đã qua"
    if delta == 0:
        return "⏰ Hạn hôm nay"
    return f"⏳ còn {delta} ngày"


def profile_summary_oneliner(profile: dict) -> str:
    if not profile:
        return "Chưa có hồ sơ sinh viên."
    return (
        f"MSSV **{profile.get('student_id')}** · {profile.get('semester')} · "
        f"Điểm hiện tại **{float(profile.get('current_total_score') or 0):g}**/"
        f"mục tiêu **{float(profile.get('target_score') or 0):g}** · "
        f"Nguồn: {config.SCORE_TYPE_LABELS.get(profile.get('score_type'), profile.get('score_type'))}"
    )


def ensure_demo_seed() -> None:
    """Gọi 1 lần khi khởi động app: tạo DB + seed dữ liệu [DEMO] nếu trống."""
    database.init_db()
    stats = database.dashboard_stats()
    if stats["n_posts"] == 0 and stats["n_criteria"] == 0:
        seed_data.seed_database()


def ai_settings_from_session() -> tuple[str, str, str]:
    return (
        st.session_state.get("ai_provider", "LOCAL"),
        st.session_state.get("ai_key", ""),
        st.session_state.get("ai_model", ""),
    )


def criteria_records() -> list[dict]:
    return database.get_criteria().fillna("").to_dict("records")
