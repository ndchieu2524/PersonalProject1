"""Lớp truy cập SQLite cho Smart DRL Assistant (MVP).

- Tự động tạo file ``smart_drl_mvp.db`` và toàn bộ schema khi khởi động.
- Toàn bộ thao tác đi qua ``get_connection()`` để bật FOREIGN KEY + row_factory.
- Các hàm ``insert_*`` / ``update_*`` trả về id để UI dùng lại.

Ghi chú MVP: theo chỉ đạo của giảng viên, hệ thống CHẤP NHẬN dữ liệu trùng lặp
(Skip Complex Deduplication). Mỗi bài đăng vẫn được lưu kèm ``content_hash``
(SHA-256) làm tiền đề nâng cấp chống trùng ở phiên bản sau, nhưng KHÔNG chặn
việc ghi trùng.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from . import config

VN_TZ = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# Kết nối & khởi tạo schema
# ---------------------------------------------------------------------------
def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Mở kết nối SQLite (tự tạo file nếu chưa có)."""
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def transaction(db_path: Optional[Path | str] = None):
    """Context manager: commit khi thành công, rollback khi lỗi."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = """
-- Bảng 1: Nguồn dữ liệu (mặc định fanpage OSA HCMUS)
CREATE TABLE IF NOT EXISTS Sources (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    url               TEXT NOT NULL,
    source_type       TEXT NOT NULL DEFAULT 'facebook_page',
    connection_status TEXT NOT NULL DEFAULT 'MANUAL',
    last_synced_at    TEXT
);

-- Bảng 2: Bài đăng thô thu thập được
CREATE TABLE IF NOT EXISTS SourcePosts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER REFERENCES Sources(id),
    external_post_id    TEXT,
    url                 TEXT,
    published_at        TEXT,
    collected_at        TEXT NOT NULL,
    raw_text            TEXT NOT NULL,
    content_hash        TEXT NOT NULL,
    fetch_method        TEXT NOT NULL,
    relevance_label     TEXT,
    rejection_reason    TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL
);

-- Bảng 3: Hoạt động bóc tách từ bài đăng
CREATE TABLE IF NOT EXISTS Activities (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_post_id        INTEGER REFERENCES SourcePosts(id),
    parent_activity_id    INTEGER REFERENCES Activities(id),
    title                 TEXT NOT NULL,
    description           TEXT,
    organizer             TEXT,
    location              TEXT,
    campus                TEXT,
    start_time            TEXT,
    end_time              TEXT,
    duration_minutes      INTEGER,
    speaker               TEXT,
    start_raw             TEXT,
    end_raw               TEXT,
    registration_deadline TEXT,
    expected_score        REAL,
    criterion_code        TEXT,
    relevance_label       TEXT NOT NULL DEFAULT 'EVENT_CANDIDATE',
    verification_status   TEXT NOT NULL DEFAULT 'UNVERIFIED',
    is_missing_time       INTEGER NOT NULL DEFAULT 0,
    is_missing_location   INTEGER NOT NULL DEFAULT 0,
    is_missing_content    INTEGER NOT NULL DEFAULT 0,
    is_missing_score      INTEGER NOT NULL DEFAULT 0,
    ai_explanation        TEXT,
    ai_source             TEXT,
    is_demo               INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL
);

-- Bảng 4: Danh mục tiêu chí ĐRL (đồng bộ từ hcmus.drl.vn)
CREATE TABLE IF NOT EXISTS DRLCriteria (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT NOT NULL,
    name             TEXT NOT NULL,
    category         TEXT,
    max_score        REAL NOT NULL DEFAULT 0,
    mandatory        INTEGER NOT NULL DEFAULT 0,
    evidence_required TEXT,
    rule_reference   TEXT,
    is_demo          INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT
);

-- Bảng 5: Hồ sơ sinh viên theo học kỳ
CREATE TABLE IF NOT EXISTS StudentProfile (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT NOT NULL,
    full_name             TEXT,
    faculty               TEXT,
    semester              TEXT NOT NULL,
    current_total_score   REAL NOT NULL DEFAULT 0,
    score_type            TEXT NOT NULL DEFAULT 'SELF_DECLARED',
    target_score          REAL NOT NULL DEFAULT 0,
    has_detailed_criteria INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT NOT NULL
);

-- Bảng 6: Tiến độ từng tiêu chí ĐRL của sinh viên
CREATE TABLE IF NOT EXISTS StudentCriterionProgress (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    semester       TEXT NOT NULL,
    criterion_code TEXT NOT NULL,
    current_score  REAL NOT NULL DEFAULT 0,
    max_score      REAL NOT NULL DEFAULT 0,
    status         TEXT,
    updated_at     TEXT NOT NULL,
    UNIQUE (student_id, semester, criterion_code)
);

-- Bảng 7: Thời khóa biểu đồng bộ từ portal.ctdb.hcmus.edu.vn
CREATE TABLE IF NOT EXISTS StudentSchedule (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    semester      TEXT,
    course_code   TEXT NOT NULL,
    course_name   TEXT,
    day_of_week   TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    room          TEXT,
    campus        TEXT,
    synced_from   TEXT NOT NULL DEFAULT 'HCMUS_CHROME_EXTENSION_V1',
    is_demo       INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL
);

-- Bảng 8: Nhật ký thao tác (audit)
CREATE TABLE IF NOT EXISTS AuditLogs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL
);

-- Bảng phụ (hỗ trợ lưu vết AI):
CREATE TABLE IF NOT EXISTS AIAnalyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER REFERENCES SourcePosts(id),
    ai_provider TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_hash      ON SourcePosts(content_hash);
CREATE INDEX IF NOT EXISTS idx_posts_label     ON SourcePosts(relevance_label);
CREATE INDEX IF NOT EXISTS idx_act_label       ON Activities(relevance_label);
CREATE INDEX IF NOT EXISTS idx_act_verify      ON Activities(verification_status);
CREATE INDEX IF NOT EXISTS idx_progress_student ON StudentCriterionProgress(student_id, semester);
CREATE INDEX IF NOT EXISTS idx_schedule_student ON StudentSchedule(student_id);
"""


#: Cột thêm sau khi phát hành – tự động migrate cho DB cũ (không mất dữ liệu).
MIGRATION_COLUMNS = {
    "duration_minutes": "INTEGER",
    "speaker": "TEXT",
    "start_raw": "TEXT",
    "end_raw": "TEXT",
}


def _migrate(conn) -> list[str]:
    """Thêm các cột còn thiếu vào bảng có sẵn. Trả về danh sách cột đã thêm."""
    added = []
    for table in ("Activities", "SourcePosts"):
        try:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        except Exception:  # noqa: BLE001 – bảng chưa tồn tại
            continue
        for col, coltype in MIGRATION_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                added.append(f"{table}.{col}")
    return added


def init_db(db_path: Optional[Path | str] = None) -> Path:
    """Tạo toàn bộ bảng nếu chưa tồn tại. Trả về đường dẫn DB thực tế.

    DB cũ được migrate tại chỗ để thêm cột mới (giữ nguyên dữ liệu đã có).
    """
    path = Path(db_path) if db_path else config.DB_PATH
    with transaction(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
    return path


# ---------------------------------------------------------------------------
# Tiện ích chung
# ---------------------------------------------------------------------------
def utcnow_iso() -> str:
    """Thời điểm hiện tại theo múi giờ Việt Nam, chuẩn ISO 8601."""
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def today_str() -> str:
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def content_hash(text: str) -> str:
    """SHA-256 của văn bản (đã chuẩn hoá khoảng trắng) – tiền đề chống trùng."""
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def row_to_dict(row: sqlite3.Row | None) -> dict:
    return dict(row) if row is not None else {}


def query_df(sql: str, params: Iterable[Any] = (), db_path: Optional[Path | str] = None) -> pd.DataFrame:
    """Chạy SELECT và trả về DataFrame (rỗng nếu không có dòng nào)."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=list(params))
    finally:
        conn.close()


def scalar(sql: str, params: Iterable[Any] = (), db_path: Optional[Path | str] = None, default=None):
    conn = get_connection(db_path)
    try:
        row = conn.execute(sql, list(params)).fetchone()
        return row[0] if row is not None else default
    finally:
        conn.close()


def log_action(action: str, details: str | dict, db_path: Optional[Path | str] = None) -> None:
    """Ghi AuditLogs – mọi thao tác quan trọng đều được lưu vết."""
    if isinstance(details, (dict, list)):
        details = json.dumps(details, ensure_ascii=False)
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO AuditLogs(action, details, created_at) VALUES (?,?,?)",
            (action, details, utcnow_iso()),
        )


def recent_audit(limit: int = 30, db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df(
        "SELECT action, details, created_at FROM AuditLogs ORDER BY id DESC LIMIT ?",
        (limit,),
        db_path,
    )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def ensure_default_source(db_path: Optional[Path | str] = None) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM Sources WHERE url = ?", (config.OSA_FACEBOOK_URL,)
        ).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO Sources(name, url, source_type, connection_status, last_synced_at) "
            "VALUES (?,?,?,?,?)",
            (
                "Fanpage OSA HCMUS (Facebook)",
                config.OSA_FACEBOOK_URL,
                "facebook_page",
                "MANUAL_ONLY (Graph API giới hạn quyền)",
                None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def create_source(name: str, url: str, source_type: str = "public_web",
                  connection_status: str = "AUTO_CRAWL",
                  db_path: Optional[Path | str] = None) -> int:
    """Tạo mới (hoặc lấy lại) một nguồn theo URL. Trả về source_id.

    Dùng cho bộ thu thập tự động: mỗi cổng công khai của trường là một nguồn.
    """
    with transaction(db_path) as conn:
        row = conn.execute("SELECT id FROM Sources WHERE url = ?", (url,)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO Sources(name, url, source_type, connection_status, last_synced_at) "
            "VALUES (?,?,?,?,?)",
            (name, url, source_type, connection_status, utcnow_iso()),
        )
        return int(cur.lastrowid)


def get_sources(db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df("SELECT * FROM Sources ORDER BY id", (), db_path)


def touch_source(source_id: int, db_path: Optional[Path | str] = None) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "UPDATE Sources SET last_synced_at = ? WHERE id = ?", (utcnow_iso(), source_id)
        )


# ---------------------------------------------------------------------------
# SourcePosts
# ---------------------------------------------------------------------------
def insert_source_post(
    source_id: int,
    raw_text: str,
    url: str | None,
    fetch_method: str,
    external_post_id: str | None = None,
    published_at: str | None = None,
    relevance_label: str | None = None,
    rejection_reason: str | None = None,
    is_demo: bool = False,
    db_path: Optional[Path | str] = None,
) -> int:
    """Lưu 1 bài đăng thô. LUÔN ghi mới (cho phép trùng – đúng chủ trương MVP)."""
    now = utcnow_iso()
    with transaction(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO SourcePosts(source_id, external_post_id, url, published_at,
                   collected_at, raw_text, content_hash, fetch_method, relevance_label,
                   rejection_reason, is_demo, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id,
                external_post_id,
                url,
                published_at,
                now,
                raw_text,
                content_hash(raw_text),
                fetch_method,
                relevance_label,
                rejection_reason,
                1 if is_demo else 0,
                now,
            ),
        )
        return int(cur.lastrowid)


def update_post_label(post_id: int, label: str, reason: str | None = None,
                      db_path: Optional[Path | str] = None) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "UPDATE SourcePosts SET relevance_label = ?, rejection_reason = ? WHERE id = ?",
            (label, reason, post_id),
        )


def get_posts(db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df("SELECT * FROM SourcePosts ORDER BY id DESC", (), db_path)


def get_post(post_id: int, db_path: Optional[Path | str] = None) -> dict:
    conn = get_connection(db_path)
    try:
        return row_to_dict(conn.execute("SELECT * FROM SourcePosts WHERE id=?", (post_id,)).fetchone())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------
ACTIVITY_INSERT_COLUMNS = [
    "source_post_id", "parent_activity_id", "title", "description", "organizer",
    "location", "campus", "start_time", "end_time", "duration_minutes",
    "speaker", "start_raw", "end_raw", "registration_deadline",
    "expected_score", "criterion_code", "relevance_label", "verification_status",
    "is_missing_time", "is_missing_location", "is_missing_content", "is_missing_score",
    "ai_explanation", "ai_source", "is_demo",
]


def insert_activity(activity: dict, db_path: Optional[Path | str] = None) -> int:
    """Chèn 1 hoạt động. ``activity`` là dict theo ACTIVITY_INSERT_COLUMNS."""
    payload = {k: activity.get(k) for k in ACTIVITY_INSERT_COLUMNS}
    payload["is_demo"] = 1 if activity.get("is_demo") else 0
    payload["created_at"] = utcnow_iso()
    cols = list(payload.keys())
    placeholders = ",".join(["?"] * len(cols))
    with transaction(db_path) as conn:
        cur = conn.execute(
            f"INSERT INTO Activities({','.join(cols)}) VALUES ({placeholders})",
            [payload[c] for c in cols],
        )
        return int(cur.lastrowid)


def update_activity(activity_id: int, updates: dict,
                    db_path: Optional[Path | str] = None) -> None:
    allowed = {k: v for k, v in updates.items() if k in set(ACTIVITY_INSERT_COLUMNS) | {"created_at"}}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    with transaction(db_path) as conn:
        conn.execute(f"UPDATE Activities SET {sets} WHERE id = ?",
                     [*allowed.values(), activity_id])


def count_duplicates(db_path: Optional[Path | str] = None) -> dict:
    """Đếm số hoạt động trùng theo ``external_post_id`` hoặc theo tiêu đề+ngày.

    Bản ghi trùng KHÔNG tự động xoá (chính sách MVP: cho phép trùng). Hàm này chỉ
    cung cấp số liệu để người dùng quyết định có gộp hay không.
    """
    conn = get_connection(db_path)
    try:
        by_external = conn.execute(
            """SELECT COALESCE(SUM(c - 1), 0) FROM (
                   SELECT COUNT(*) AS c FROM SourcePosts
                   WHERE external_post_id IS NOT NULL AND external_post_id <> ''
                   GROUP BY external_post_id HAVING c > 1)"""
        ).fetchone()[0]
        by_title = conn.execute(
            """SELECT COALESCE(SUM(c - 1), 0) FROM (
                   SELECT COUNT(*) AS c FROM Activities
                   WHERE is_demo = 0
                   GROUP BY LOWER(TRIM(REPLACE(REPLACE(title, '“', '"'), '”', '"')))
                   HAVING c > 1)"""
        ).fetchone()[0]
        return {
            "dup_by_post_id": int(by_external or 0),
            "dup_by_title": int(by_title or 0),
        }
    finally:
        conn.close()


def merge_duplicates(db_path: Optional[Path | str] = None) -> dict:
    """GỘP hoạt động trùng: giữ bản ghi có ĐIỂM CAO NHẤT trong nhóm, xoá bản còn lại.

    Nhóm xác định theo (tiêu đề chuẩn hoá, ngày bắt đầu). Chỉ xét ``is_demo = 0``
    để không bao giờ đụng vào dữ liệu mẫu. Bản được giữ sẽ được bổ sung các trường
    còn trống từ bản bị xoá (địa điểm, đơn vị, giờ kết thúc) — không ghi đè dữ liệu
    đã có, không bịa thêm.
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM Activities WHERE is_demo = 0 ORDER BY id"""
        ).fetchall()
    finally:
        conn.close()
    def _norm_title(value: str) -> str:
        """Chuẩn hoá mạnh để nhận ra cùng một hoạt động do nhiều nguồn đăng."""
        import re
        import unicodedata

        txt = str(value or "").lower()
        txt = unicodedata.normalize("NFD", txt)
        txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
        txt = re.sub(r"[^a-z0-9\s]", " ", txt)
        return re.sub(r"\s+", " ", txt).strip()

    groups: dict[tuple, list] = {}
    for row in rows:
        rec = row_to_dict(row)
        # Nhóm theo TIÊU ĐỀ đã chuẩn hoá (bỏ dấu, bỏ ký tự đặc biệt). Ngày không
        # đưa vào khoá vì cùng một hoạt động có thể bị nguồn này ghi ngày, nguồn
        # kia bỏ trống — nếu ghép cả ngày sẽ bỏ sót trùng.
        key = (_norm_title(rec.get("title")),)
        groups.setdefault(key, []).append(rec)

    n_merged = 0
    n_deleted = 0
    for key, items in groups.items():
        if len(items) < 2:
            continue
        # Giữ bản có điểm cao nhất; hoà thì giữ bản đầy đủ thông tin hơn
        items.sort(key=lambda r: (
            float(r.get("expected_score") or -1),
            sum(1 for f in ("start_time", "end_time", "location", "organizer", "criterion_code")
                if r.get(f)),
        ), reverse=True)
        keep, drop = items[0], items[1:]
        patch = {}
        for field_name in ("start_time", "end_time", "location", "campus",
                           "organizer", "criterion_code", "registration_deadline"):
            if not keep.get(field_name):
                for other in drop:
                    if other.get(field_name):
                        patch[field_name] = other[field_name]
                        break
        if patch:
            update_activity(int(keep["id"]), patch, db_path)
        for other in drop:
            with transaction(db_path) as conn:
                conn.execute("DELETE FROM Activities WHERE id = ?", (int(other["id"]),))
            n_deleted += 1
        n_merged += 1

    log_action("MERGE_DUPLICATES", {"groups": n_merged, "deleted": n_deleted}, db_path)
    return {"groups_merged": n_merged, "rows_deleted": n_deleted}


def purge_expired_real_activities(db_path: Optional[Path | str] = None) -> dict:
    """Xoá các hoạt động THẬT đã kết thúc (chỉ is_demo = 0, giữ nguyên dữ liệu mẫu).

    Dùng khi kho bị lẫn sự kiện cũ do lượt thu thập trước lấy toàn bộ lịch sử.
    Mục không rõ ngày được GIỮ LẠI (không đủ căn cứ để kết luận đã diễn ra).
    """
    from datetime import datetime

    now = datetime.now()
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, title, start_time, end_time FROM Activities WHERE is_demo = 0"
        ).fetchall()
    finally:
        conn.close()

    expired_ids: list[int] = []
    for row in rows:
        rec = {"start_time": row["start_time"], "end_time": row["end_time"]}
        end_raw = str(rec["end_time"] or "") or str(rec["start_time"] or "")
        if len(end_raw) < 10:
            continue
        end_dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                end_dt = datetime.strptime(
                    end_raw[:16] if ":" in end_raw else end_raw[:10], fmt)
                break
            except ValueError:
                continue
        if end_dt is not None and end_dt.date() < now.date():
            expired_ids.append(int(row["id"]))

    if expired_ids:
        with transaction(db_path) as conn:
            conn.executemany("DELETE FROM Activities WHERE id = ?",
                             [(i,) for i in expired_ids])
    log_action("PURGE_EXPIRED", {"deleted": len(expired_ids)}, db_path)
    return {"deleted": len(expired_ids)}


def get_activities(include_demo: bool = True,
                   db_path: Optional[Path | str] = None) -> pd.DataFrame:
    sql = """
        SELECT a.*, p.url AS post_url, p.fetch_method, p.collected_at AS post_collected_at,
               p.raw_text
        FROM Activities a
        LEFT JOIN SourcePosts p ON p.id = a.source_post_id
    """
    if not include_demo:
        sql += " WHERE a.is_demo = 0"
    sql += " ORDER BY a.id DESC"
    return query_df(sql, (), db_path)


def get_activity(activity_id: int, db_path: Optional[Path | str] = None) -> dict:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """SELECT a.*, p.url AS post_url, p.fetch_method, p.raw_text
               FROM Activities a LEFT JOIN SourcePosts p ON p.id = a.source_post_id
               WHERE a.id = ?""",
            (activity_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def set_verification_status(activity_id: int, status: str, label: str | None = None,
                            note: str | None = None,
                            db_path: Optional[Path | str] = None) -> None:
    conn = get_connection(db_path)
    try:
        current = row_to_dict(conn.execute(
            "SELECT * FROM Activities WHERE id=?", (activity_id,)
        ).fetchone())
    finally:
        conn.close()
    if not current:
        return
    new_label = label if label else current.get("relevance_label")
    explanation = current.get("ai_explanation") or ""
    if note:
        explanation = (explanation + "\n\n" if explanation else "") + f"[Admin] {note}"
    update_activity(activity_id, {
        "verification_status": status,
        "relevance_label": new_label,
        "ai_explanation": explanation,
    }, db_path)
    log_action("VERIFY_ACTIVITY",
               {"activity_id": activity_id, "status": status, "note": note or ""},
               db_path)


def link_parent_activity(activity_id: int, parent_id: int | None,
                         db_path: Optional[Path | str] = None) -> None:
    update_activity(activity_id, {"parent_activity_id": parent_id}, db_path)
    log_action("LINK_PARENT_ACTIVITY",
               {"activity_id": activity_id, "parent_activity_id": parent_id}, db_path)


# ---------------------------------------------------------------------------
# DRLCriteria
# ---------------------------------------------------------------------------
def upsert_criterion(criteria: dict, db_path: Optional[Path | str] = None) -> None:
    now = utcnow_iso()
    with transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM DRLCriteria WHERE code = ?", (criteria["code"],)
        ).fetchone()
        values = (
            criteria["code"],
            criteria.get("name", ""),
            criteria.get("category", ""),
            float(criteria.get("max_score", 0) or 0),
            1 if criteria.get("mandatory") else 0,
            criteria.get("evidence_required", ""),
            criteria.get("rule_reference", ""),
            1 if criteria.get("is_demo") else 0,
            now,
        )
        if existing:
            conn.execute(
                """UPDATE DRLCriteria SET name=?, category=?, max_score=?, mandatory=?,
                       evidence_required=?, rule_reference=?, is_demo=?, updated_at=?
                   WHERE code=?""",
                (*values[1:], criteria["code"]),
            )
        else:
            conn.execute(
                """INSERT INTO DRLCriteria(code, name, category, max_score, mandatory,
                       evidence_required, rule_reference, is_demo, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                values,
            )


def get_criteria(db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df("SELECT * FROM DRLCriteria ORDER BY code", (), db_path)


def get_criteria_dict(db_path: Optional[Path | str] = None) -> dict[str, dict]:
    df = get_criteria(db_path)
    return {row["code"]: row for row in df.to_dict("records")}


# ---------------------------------------------------------------------------
# StudentProfile
# ---------------------------------------------------------------------------
def upsert_profile(profile: dict, db_path: Optional[Path | str] = None) -> int:
    """Ghi đè hồ sơ của (student_id, semester); trả về id."""
    now = utcnow_iso()
    sid = str(profile["student_id"]).strip()
    semester = str(profile["semester"]).strip()
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM StudentProfile WHERE student_id=? AND semester=?",
            (sid, semester),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE StudentProfile SET full_name=?, faculty=?, current_total_score=?,
                       score_type=?, target_score=?, has_detailed_criteria=?, updated_at=?
                   WHERE id=?""",
                (
                    profile.get("full_name", ""),
                    profile.get("faculty", ""),
                    float(profile.get("current_total_score", 0) or 0),
                    profile.get("score_type", config.SCORE_TYPE_SELF_DECLARED),
                    float(profile.get("target_score", 0) or 0),
                    1 if profile.get("has_detailed_criteria") else 0,
                    now,
                    int(row["id"]),
                ),
            )
            return int(row["id"])
        cur = conn.execute(
            """INSERT INTO StudentProfile(student_id, full_name, faculty, semester,
                   current_total_score, score_type, target_score, has_detailed_criteria, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                sid,
                profile.get("full_name", ""),
                profile.get("faculty", ""),
                semester,
                float(profile.get("current_total_score", 0) or 0),
                profile.get("score_type", config.SCORE_TYPE_SELF_DECLARED),
                float(profile.get("target_score", 0) or 0),
                1 if profile.get("has_detailed_criteria") else 0,
                now,
            ),
        )
        return int(cur.lastrowid)


def get_profile(student_id: str, semester: str | None = None,
                db_path: Optional[Path | str] = None) -> dict:
    conn = get_connection(db_path)
    try:
        if semester:
            row = conn.execute(
                "SELECT * FROM StudentProfile WHERE student_id=? AND semester=? "
                "ORDER BY updated_at DESC LIMIT 1",
                (student_id, semester),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM StudentProfile WHERE student_id=? ORDER BY updated_at DESC LIMIT 1",
                (student_id,),
            ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_profiles(db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df(
        "SELECT * FROM StudentProfile ORDER BY updated_at DESC", (), db_path
    )


def latest_profile(db_path: Optional[Path | str] = None) -> dict:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM StudentProfile ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# StudentCriterionProgress
# ---------------------------------------------------------------------------
def replace_criterion_progress(student_id: str, semester: str, rows: list[dict],
                               db_path: Optional[Path | str] = None) -> int:
    """Thay toàn bộ tiến độ tiêu chí của (student_id, semester). Trả về số dòng."""
    now = utcnow_iso()
    with transaction(db_path) as conn:
        conn.execute(
            "DELETE FROM StudentCriterionProgress WHERE student_id=? AND semester=?",
            (student_id, semester),
        )
        conn.executemany(
            """INSERT INTO StudentCriterionProgress(student_id, semester, criterion_code,
                   current_score, max_score, status, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            [
                (
                    student_id,
                    semester,
                    r["criterion_code"],
                    float(r.get("current_score", 0) or 0),
                    float(r.get("max_score", 0) or 0),
                    r.get("status", ""),
                    now,
                )
                for r in rows
            ],
        )
    return len(rows)


def get_criterion_progress(student_id: str, semester: str,
                           db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df(
        """SELECT pr.criterion_code, COALESCE(c.name, pr.criterion_code) AS name,
                  COALESCE(c.category, '') AS category,
                  pr.current_score, pr.max_score, pr.status,
                  COALESCE(c.mandatory, 0) AS mandatory
           FROM StudentCriterionProgress pr
           LEFT JOIN DRLCriteria c ON c.code = pr.criterion_code
           WHERE pr.student_id = ? AND pr.semester = ?
           ORDER BY pr.criterion_code""",
        (student_id, semester),
        db_path,
    )


# ---------------------------------------------------------------------------
# StudentSchedule
# ---------------------------------------------------------------------------
def replace_schedule(student_id: str, semester: str, rows: list[dict],
                     synced_from: str = config.SYNC_SOURCE_TAG,
                     is_demo: bool = False,
                     db_path: Optional[Path | str] = None) -> int:
    now = utcnow_iso()
    with transaction(db_path) as conn:
        conn.execute("DELETE FROM StudentSchedule WHERE student_id=?", (student_id,))
        conn.executemany(
            """INSERT INTO StudentSchedule(student_id, semester, course_code, course_name,
                   day_of_week, start_time, end_time, room, campus, synced_from, is_demo, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    student_id,
                    semester,
                    r.get("course_code", ""),
                    r.get("course_name", ""),
                    r.get("day_of_week", ""),
                    r.get("start_time", ""),
                    r.get("end_time", ""),
                    r.get("room", ""),
                    r.get("campus", "NVC"),
                    r.get("synced_from", synced_from),
                    1 if is_demo else 0,
                    now,
                )
                for r in rows
            ],
        )
    return len(rows)


def get_schedule(student_id: str, db_path: Optional[Path | str] = None) -> pd.DataFrame:
    return query_df(
        """SELECT * FROM StudentSchedule WHERE student_id = ?
           ORDER BY CASE day_of_week
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7 ELSE 8 END, start_time""",
        (student_id,),
        db_path,
    )


# ---------------------------------------------------------------------------
# AI analyses
# ---------------------------------------------------------------------------
def save_ai_analysis(post_id: int | None, ai_provider: str, report: dict,
                     db_path: Optional[Path | str] = None) -> int:
    with transaction(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO AIAnalyses(post_id, ai_provider, report_json, created_at) VALUES (?,?,?,?)",
            (post_id, ai_provider, json.dumps(report, ensure_ascii=False), utcnow_iso()),
        )
        return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Thống kê nhanh cho Dashboard
# ---------------------------------------------------------------------------
def dashboard_stats(db_path: Optional[Path | str] = None) -> dict:
    conn = get_connection(db_path)
    try:
        def one(sql, params=()):
            r = conn.execute(sql, params).fetchone()
            return r[0] if r else 0

        return {
            "n_posts": one("SELECT COUNT(*) FROM SourcePosts"),
            "n_activities": one("SELECT COUNT(*) FROM Activities"),
            "n_verified": one("SELECT COUNT(*) FROM Activities WHERE relevance_label='VERIFIED_DRL'"),
            "n_potential": one("SELECT COUNT(*) FROM Activities WHERE relevance_label='POTENTIAL_DRL'"),
            "n_insufficient": one("SELECT COUNT(*) FROM Activities WHERE relevance_label='INSUFFICIENT_INFO'"),
            "n_not_relevant": one("SELECT COUNT(*) FROM Activities WHERE relevance_label='NOT_RELEVANT'"),
            "n_schedule": one("SELECT COUNT(*) FROM StudentSchedule"),
            "n_criteria": one("SELECT COUNT(*) FROM DRLCriteria"),
        }
    finally:
        conn.close()
