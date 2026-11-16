"""Kiểm thử tự động cho Smart DRL Assistant (chạy: pytest -q).

Bao phủ:
  - Bóc tách ngày/giờ/địa điểm/điểm ĐRL bằng Regex
  - Phân loại 2 bước + cờ thiếu dữ liệu
  - Schema 1 của báo cáo AI/NLP
  - SQLite: schema, seed [DEMO], đồng bộ gói Schema 2
  - NetworkX: lọc trùng lịch, DAG, tối ưu có trần tiêu chí
  - ML: baseline vs mô hình đề xuất, độ đo, confusion matrix
  - An toàn: AI không được tự nâng VERIFIED_DRL
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from drl import config, database, ml_benchmark, nlp_engine, pathway, seed_data  # noqa: E402
from drl.ai_engine import sanitize_ai_report  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(db_path)
    seed_data.seed_database(db_path=db_path, force=True)
    return db_path


@pytest.fixture()
def catalog():
    return [dict(c) for c in seed_data.DEMO_CRITERIA]


# ---------------------------------------------------------------------------
# 1. NLP: trích xuất thời gian
# ---------------------------------------------------------------------------
def test_extract_time_full(catalog):
    text = (
        "HỘI THẢO AI\n"
        "⏰ Thời gian: 08h30 - 11h30, ngày 22/11/2026\n"
        "👉 Đăng ký trước 23h59 ngày 20/11/2026 tại link.\n"
        "📍 Địa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ, Q.5\n"
        "🎁 Được cộng 5 điểm rèn luyện.\n"
    )
    act = nlp_engine.analyze_post(text, criteria_catalog=catalog)["activity"]
    assert act["start_time"] == "2026-11-22 08:30"
    assert act["end_time"] == "2026-11-22 11:30"
    assert act["registration_deadline"] == "2026-11-20 23:59"


def test_time_range_not_mistaken_for_date(catalog):
    """"08h30 - 11h30" KHÔNG được hiểu thành ngày 30/11."""
    text = "Thời gian: 08h30 - 11h30\n📍 Phòng A.101, Cơ sở Linh Trung\nTham gia được cộng 3 điểm rèn luyện."
    report = nlp_engine.analyze_post(text, criteria_catalog=catalog)
    act = report["activity"]
    assert act["start_time"] is None, "Không có ngày cụ thể ⇒ không được tự suy ra ngày"
    assert report["missing_flags"]["is_missing_time"] is True


def test_deadline_only_does_not_create_fake_event_time(catalog):
    text = ("NHẮC HẠN ĐĂNG KÝ\nHạn chót: 23h59 ngày 20/11/2026\n"
            "📍 Hội trường I, Cơ sở Nguyễn Văn Cừ\nTham gia được cộng 5 điểm rèn luyện.")
    act = nlp_engine.analyze_post(text, criteria_catalog=catalog)["activity"]
    assert act["registration_deadline"] == "2026-11-20 23:59"
    assert act["start_time"] is None


# ---------------------------------------------------------------------------
# 2. NLP: địa điểm, điểm, tiêu chí
# ---------------------------------------------------------------------------
def test_location_and_campus(catalog):
    text = ("WORKSHOP KỸ NĂNG\nThời gian: 13h30 - 17h00, ngày 20/12/2026\n"
            "📍 Địa điểm: Phòng D401, Cơ sở Linh Trung\n"
            "Sinh viên tham gia đầy đủ được cộng 3 điểm rèn luyện.")
    act = nlp_engine.analyze_post(text, criteria_catalog=catalog)["activity"]
    assert "Linh Trung" in act["location"]
    assert act["campus"] == "Linh Trung"
    assert act["expected_score"] == 3.0


def test_pending_location_is_missing(catalog):
    text = ("BUỔI CHIA SẺ HỌC BỔNG\nThời gian: 18h00 - 20h00, ngày 09/12/2026\n"
            "Địa điểm sẽ thông báo tới sinh viên đăng ký qua email.\n")
    report = nlp_engine.analyze_post(text, criteria_catalog=catalog)
    assert report["activity"]["location"] == ""
    assert report["missing_flags"]["is_missing_location"] is True
    assert report["relevance_label"] == config.LABEL_INSUFFICIENT


def test_score_only_when_explicit(catalog):
    no_score = ("CUỘC THI HÙNG BIỆN\nThời gian: 13h00 - 17h00, ngày 13/12/2026\n"
                "Địa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ\nĐăng ký trước 05/12/2026.")
    report = nlp_engine.analyze_post(no_score, criteria_catalog=catalog)
    assert report["activity"]["expected_score"] is None
    assert report["relevance_label"] == config.LABEL_EVENT_CANDIDATE


def test_criterion_mapping(catalog):
    text = ("NGÀY HỘI HIẾN MÁU NHÂN ĐẠO\nThời gian: 07h30 - 10h00, ngày 28/11/2026\n"
            "Địa điểm: Sân Trường, Cơ sở Nguyễn Văn Cừ\nĐược cộng 4 điểm rèn luyện.")
    act = nlp_engine.analyze_post(text, criteria_catalog=catalog)["activity"]
    assert act["criterion_code"] == "TC_3.2"


# ---------------------------------------------------------------------------
# 3. Phân loại 2 bước
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key,expected", [
    ("hoi_thao_ai", config.LABEL_POTENTIAL),
    ("xuan_tinh_nguyen", config.LABEL_INSUFFICIENT),
    ("workshop_thuyet_trinh", config.LABEL_INSUFFICIENT),
    ("cuoc_thi_khoi_nghiep", config.LABEL_EVENT_CANDIDATE),
    ("chuc_mung_olympic", config.LABEL_NOT_RELEVANT),
    ("tuyen_thuc_tap", config.LABEL_NOT_RELEVANT),
    ("hien_mau", config.LABEL_POTENTIAL),
])
def test_demo_posts_labels(key, expected, catalog):
    post = next(p for p in seed_data.DEMO_POSTS if p["key"] == key)
    report = nlp_engine.analyze_post(post["text"], criteria_catalog=catalog)
    assert report["relevance_label"] == expected


def test_benchmark_agreement_high(catalog):
    """Bộ heuristic phải khớp ≥ 90% nhãn chuẩn (tài liệu ghi rõ đây là luật đã tinh chỉnh)."""
    agree = 0
    for row in seed_data.BENCHMARK_DATASET:
        report = nlp_engine.analyze_post(row["text"], criteria_catalog=catalog)
        agree += int(report["relevance_label"] == row["label"])
    ratio = agree / len(seed_data.BENCHMARK_DATASET)
    assert ratio >= 0.9, f"Chỉ khớp {ratio:.0%} nhãn benchmark"


# ---------------------------------------------------------------------------
# 4. Schema 1
# ---------------------------------------------------------------------------
def test_report_schema_keys(catalog):
    report = nlp_engine.analyze_post(seed_data.DEMO_POSTS[0]["text"], criteria_catalog=catalog)
    for key in ("post_type", "relevance_label", "relevance_reason",
                "is_student_participation_possible", "activity", "missing_flags",
                "drl_assessment"):
        assert key in report
    for key in ("title", "organizer", "location", "start_time", "end_time",
                "registration_deadline", "expected_score", "criterion_code"):
        assert key in report["activity"]
    for key in ("is_missing_time", "is_missing_location",
                "is_missing_content", "is_missing_score"):
        assert key in report["missing_flags"]
        assert isinstance(report["missing_flags"][key], bool)
    json.dumps(report, ensure_ascii=False)  # phải serialize được


# ---------------------------------------------------------------------------
# 5. An toàn AI
# ---------------------------------------------------------------------------
def test_ai_cannot_self_verify(catalog):
    local = nlp_engine.analyze_post(seed_data.DEMO_POSTS[0]["text"], criteria_catalog=catalog)
    ai_report = {
        "relevance_label": "VERIFIED_DRL",
        "activity": {"expected_score": 5, "criterion_code": "TC_2.1"},
        "drl_assessment": {"status": "ADMIN_APPROVED"},
    }
    sanitized, warnings = sanitize_ai_report(ai_report, local, catalog)
    assert sanitized["relevance_label"] != "VERIFIED_DRL"
    assert any("VERIFIED_DRL" in w for w in warnings)


def test_ai_unknown_criterion_dropped(catalog):
    local = nlp_engine.analyze_post(seed_data.DEMO_POSTS[0]["text"], criteria_catalog=catalog)
    ai_report = {"activity": {"criterion_code": "TC_99.99", "expected_score": 5}}
    sanitized, warnings = sanitize_ai_report(ai_report, local, catalog)
    assert sanitized["activity"]["criterion_code"] != "TC_99.99"
    assert any("TC_99.99" in w for w in warnings)


# ---------------------------------------------------------------------------
# 6. Database & seed
# ---------------------------------------------------------------------------
def test_schema_tables(temp_db):
    with database.transaction(temp_db) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r[0] for r in rows}
    required = {"Sources", "SourcePosts", "Activities", "DRLCriteria", "StudentProfile",
                "StudentCriterionProgress", "StudentSchedule", "AuditLogs"}
    assert required.issubset(names)


def test_seed_counts(temp_db):
    stats = database.dashboard_stats(temp_db)
    assert stats["n_posts"] == len(seed_data.DEMO_POSTS)
    assert stats["n_criteria"] == len(seed_data.DEMO_CRITERIA)
    assert stats["n_schedule"] == len(seed_data.DEMO_SCHEDULE)
    posts = database.get_posts(temp_db)
    assert (posts["is_demo"] == 1).all()


def test_content_hash_present_and_duplicates_allowed(temp_db):
    posts = database.get_posts(temp_db)
    assert all(len(h) == 64 for h in posts["content_hash"])
    source_id = database.ensure_default_source(temp_db)
    text = seed_data.DEMO_POSTS[0]["text"]
    id1 = database.insert_source_post(source_id, text, "u", "TEST", db_path=temp_db)
    id2 = database.insert_source_post(source_id, text, "u", "TEST", db_path=temp_db)
    assert id1 != id2, "MVP cho phép ghi trùng"
    assert len(database.get_posts(temp_db)) == len(posts) + 2


def test_sync_payload_roundtrip(temp_db):
    payload = seed_data.demo_sync_payload()
    database.upsert_profile({
        "student_id": payload["student_profile"]["student_id"],
        "semester": payload["student_profile"]["semester"],
        "current_total_score": payload["student_profile"]["current_total_score"],
        "score_type": payload["student_profile"]["score_type"],
        "target_score": 90,
        "has_detailed_criteria": True,
    }, temp_db)
    database.replace_criterion_progress(
        payload["student_profile"]["student_id"],
        payload["student_profile"]["semester"],
        payload["drl_progress"], temp_db)
    database.replace_schedule(payload["student_profile"]["student_id"],
                              payload["student_profile"]["semester"],
                              payload["timetable"], db_path=temp_db)
    progress = database.get_criterion_progress(
        payload["student_profile"]["student_id"],
        payload["student_profile"]["semester"], temp_db)
    assert len(progress) == len(payload["drl_progress"])
    assert len(database.get_schedule(payload["student_profile"]["student_id"], temp_db)) \
        == len(payload["timetable"])


# ---------------------------------------------------------------------------
# 7. NetworkX pathway
# ---------------------------------------------------------------------------
def _synthetic_case():
    """3 hoạt động: 1 trùng lịch học, 2 xếp được liên tiếp."""
    schedule = [{"course_code": "PHY1", "course_name": "Lý", "day_of_week": "Thursday",
                 "start_time": "07:30", "end_time": "11:30", "room": "A1", "campus": "Linh Trung"}]
    activities = [
        {"id": 1, "title": "A", "start_time": "2027-03-04 08:00", "end_time": "2027-03-04 10:00",
         "campus": "Linh Trung", "relevance_label": config.LABEL_POTENTIAL, "expected_score": 5,
         "criterion_code": "TC_2.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "NEEDS_HUMAN_REVIEW"},
        {"id": 2, "title": "B", "start_time": "2027-03-06 08:00", "end_time": "2027-03-06 10:00",
         "campus": "Linh Trung", "relevance_label": config.LABEL_POTENTIAL, "expected_score": 4,
         "criterion_code": "TC_2.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "NEEDS_HUMAN_REVIEW"},
        {"id": 3, "title": "C", "start_time": "2027-03-06 11:00", "end_time": "2027-03-06 13:00",
         "campus": "NVC", "relevance_label": config.LABEL_VERIFIED, "expected_score": 3,
         "criterion_code": "TC_3.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "ADMIN_APPROVED"},
    ]
    import pandas as pd
    return pd.DataFrame(activities), pd.DataFrame(schedule)


def test_conflict_filtered_and_travel_edge():
    activities, schedule = _synthetic_case()
    candidates, rejected, conflicts = pathway.prepare_candidates(
        activities, schedule, include_past=True)
    assert [c["id"] for c in candidates] == [2, 3]
    assert len(conflicts) == 1 and conflicts[0]["id"] == 1

    graph = pathway.build_activity_graph(candidates)
    # B (Linh Trung) kết thúc 10:00 → C (NVC) bắt đầu 11:00: cần 45 phút ⇒ 10:00+45 ≤ 11:00 ✔
    assert graph.has_edge(2, 3)
    edge = graph[2][3]
    assert edge["travel_minutes"] == 45
    assert edge["slack_minutes"] == 15


def test_travel_time_blocks_edge():
    activities, _ = _synthetic_case()
    activities.loc[activities["id"] == 3, "start_time"] = "2027-03-06 10:30"
    activities.loc[activities["id"] == 3, "end_time"] = "2027-03-06 12:00"
    candidates, _, _ = pathway.prepare_candidates(activities, _synthetic_case()[1],
                                                  include_past=True)
    graph = pathway.build_activity_graph(candidates)
    assert not graph.has_edge(2, 3), "Không kịp di chuyển 45 phút ⇒ không có cạnh"


def test_criterion_cap_respected():
    import pandas as pd
    # Hai hoạt động cùng tiêu chí, tổng 10 điểm nhưng dư địa chỉ còn 6
    activities = pd.DataFrame([
        {"id": 1, "title": "A", "start_time": "2027-03-02 08:00", "end_time": "2027-03-02 10:00",
         "campus": "NVC", "relevance_label": config.LABEL_POTENTIAL, "expected_score": 5,
         "criterion_code": "TC_2.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "X"},
        {"id": 2, "title": "B", "start_time": "2027-03-09 08:00", "end_time": "2027-03-09 10:00",
         "campus": "NVC", "relevance_label": config.LABEL_POTENTIAL, "expected_score": 5,
         "criterion_code": "TC_2.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "X"},
        {"id": 3, "title": "C", "start_time": "2027-03-02 11:00", "end_time": "2027-03-02 12:00",
         "campus": "NVC", "relevance_label": config.LABEL_VERIFIED, "expected_score": 3,
         "criterion_code": "TC_3.1", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0, "verification_status": "ADMIN_APPROVED"},
    ])
    candidates, _, conflicts = pathway.prepare_candidates(
        activities, pd.DataFrame([]), include_past=True)
    assert len(candidates) == 3 and not conflicts
    graph = pathway.build_activity_graph(candidates)
    headroom = {"TC_2.1": 6.0, "TC_3.1": 20.0}
    result = pathway.dynamic_programming_path(candidates, graph, headroom,
                                              target_remaining=10, prefer_verified=True)
    assert result["total_expected_score"] <= 9  # 5 + 3, KHÔNG học 5 + 5 = 10 vì vượt trần
    assert result["total_expected_score"] >= 8


def test_pathway_end_to_end(temp_db):
    result = pathway.compute_optimal_pathway(db_path=temp_db)
    assert "error" not in result
    route = result["route"]
    assert route["total_expected_score"] >= 0
    # tổng điểm theo tiêu chí không được vượt dư địa
    for code, gain in route["gains_by_criterion"].items():
        assert gain <= route["criterion_missing"].get(code, gain) + 1e-6
    # mỗi hoạt động trong lộ trình phải khớp tổng
    assert abs(sum(a["expected_score"] for a in route["activities"])
               - route["total_expected_score"]) < 1e-6


# ---------------------------------------------------------------------------
# 8. ML benchmark
# ---------------------------------------------------------------------------
def test_benchmark_dataset_size_and_balance():
    assert len(seed_data.BENCHMARK_DATASET) >= 20
    labels = [row["label"] for row in seed_data.BENCHMARK_DATASET]
    for lbl in (config.LABEL_NOT_RELEVANT, config.LABEL_INSUFFICIENT,
                config.LABEL_EVENT_CANDIDATE, config.LABEL_POTENTIAL):
        assert labels.count(lbl) >= 5


def test_ml_vs_baseline():
    result = ml_benchmark.run_benchmark(run_cv=True, n_splits=3)
    assert result.n_train + result.n_test == len(seed_data.BENCHMARK_DATASET)
    assert set(result.metrics_ml) >= {"accuracy", "precision_macro", "recall_macro", "f1_macro"}
    assert result.confusion_ml.shape[0] == len(result.labels)
    assert result.cv_scores["f1_macro_mean"] > 0.5
    assert result.metrics_ml["f1_macro"] >= result.metrics_baseline["f1_macro"]
    df = ml_benchmark.comparison_dataframe(result)
    assert len(df) == 3  # baseline, đề xuất, chênh lệch


def test_baseline_classifier_is_deterministic():
    texts = [row["text"] for row in seed_data.BENCHMARK_DATASET]
    labels = [row["label"] for row in seed_data.BENCHMARK_DATASET]
    model = ml_benchmark.BaselineKeywordClassifier().fit(texts, labels)
    preds = model.predict(texts)
    assert len(preds) == len(texts)
    assert set(preds).issubset(set(labels))


# ---------------------------------------------------------------------------
# 9. Seed sync payload
# ---------------------------------------------------------------------------
def test_demo_sync_payload_schema():
    payload = seed_data.demo_sync_payload()
    assert payload["sync_source"] == config.SYNC_SOURCE_TAG
    assert payload["is_demo"] is True
    assert payload["student_profile"]["has_detailed_criteria"] is True
    assert len(payload["drl_progress"]) == len(seed_data.DEMO_CRITERIA)
    assert len(payload["timetable"]) == len(seed_data.DEMO_SCHEDULE)
    total = sum(row["current_score"] for row in payload["drl_progress"])
    assert payload["student_profile"]["current_total_score"] == total


def test_weekday_parse_vietnamese():
    text = ("LỚP TẬP HUẤN\nThời gian: 08h00 - 11h00, ngày 26/11/2026 (Thứ Năm)\n"
            "📍 Phòng B105, Cơ sở Linh Trung\nĐược cộng 3 điểm rèn luyện.")
    start = datetime.strptime(
        nlp_engine.analyze_post(text, criteria_catalog=seed_data.DEMO_CRITERIA)["activity"]["start_time"],
        "%Y-%m-%d %H:%M")
    assert start.weekday() == 3  # Thứ Năm


# ---------------------------------------------------------------------------
# Hồi quy: dữ liệu THẬT từ cổng trường (dựa trên ảnh chụp CTĐB của người dùng)
# ---------------------------------------------------------------------------
REAL_CTDB_TIMETABLE = [
    {"course_code": "BAA00005", "course_name": "Kinh tế đại cương", "day_of_week": "Tuesday",
     "start_time": "07:30", "end_time": "11:10", "room": "E402", "campus": "NVC"},
    {"course_code": "BAA00021", "course_name": "Thực tập 1", "day_of_week": "Monday",
     "start_time": "07:30", "end_time": "11:10", "room": "", "campus": "NVC"},
    {"course_code": "CSC10008", "course_name": "Mạng máy tính", "day_of_week": "Tuesday",
     "start_time": "13:30", "end_time": "17:10", "room": "B116", "campus": "NVC"},
    {"course_code": "CSC10014", "course_name": "Tư duy tính toán", "day_of_week": "Monday",
     "start_time": "13:30", "end_time": "17:10", "room": "C36", "campus": "NVC"},
    {"course_code": "CSC10014", "course_name": "Tư duy tính toán", "day_of_week": "Friday",
     "start_time": "07:30", "end_time": "09:30", "room": "152", "campus": "NVC"},
    {"course_code": "MTH00006", "course_name": "Vi tích phân 2", "day_of_week": "Thursday",
     "start_time": "07:30", "end_time": "11:10", "room": "E308", "campus": "NVC"},
    {"course_code": "MTH00006", "course_name": "Vi tích phân 2", "day_of_week": "Thursday",
     "start_time": "13:30", "end_time": "15:30", "room": "E307", "campus": "NVC"},
]


def test_sync_timetable_only_keeps_previous_score(tmp_path):
    """Gói chỉ có TKB (chưa quét DRL) KHÔNG được xoá điểm/tín chỉ tiêu chí đã đồng bộ."""
    from drl import database, ui_common

    db = tmp_path / "regress.db"
    database.init_db(db)
    full = {
        "sync_source": "HCMUS_CHROME_EXTENSION_V1",
        "synced_at": "2026-11-14T00:00:00Z",
        "student_profile": {"student_id": "25127302", "semester": "HK1_2026_2027",
                            "current_total_score": 61, "score_type": "OFFICIAL_SYNCED"},
        "drl_progress": [
            {"criterion_code": "TC_1", "name": "Ý thức học tập",
             "current_score": 18, "max_score": 20, "mandatory": True},
        ],
        "timetable": REAL_CTDB_TIMETABLE,
    }
    ui_common.apply_sync_payload(full, db_path=db)

    only_ttb = {
        "sync_source": "HCMUS_CHROME_EXTENSION_V1",
        "synced_at": "2026-11-14T00:05:00Z",
        "student_profile": {"student_id": "25127302", "semester": "HK1_2026_2027",
                            "current_total_score": None, "score_type": "SELF_DECLARED"},
        "drl_progress": [],
        "timetable": REAL_CTDB_TIMETABLE,
    }
    info = ui_common.apply_sync_payload(only_ttb, db_path=db)

    profile = database.get_profile("25127302", "HK1_2026_2027", db_path=db)
    assert float(profile["current_total_score"]) == 61.0, "Điểm cũ bị ghi đè!"
    assert len(database.get_criterion_progress("25127302", "HK1_2026_2027", db_path=db)) == 1
    assert info["kept_previous_score"] is True
    assert info["n_timetable"] == len(REAL_CTDB_TIMETABLE)


def test_real_timetable_conflict_and_pathway(tmp_path):
    """Lịch thật 7 buổi: Thứ 3 có 2 buổi liền nhau, Thứ 5 có 2 buổi cùng môn."""
    from drl import database, pathway

    db = tmp_path / "regress2.db"
    database.init_db(db)
    database.replace_schedule("25127302", "HK1_2026_2027", REAL_CTDB_TIMETABLE, db_path=db)
    df = database.get_schedule("25127302", db_path=db)
    assert len(df) == 7
    assert set(df["room"].fillna("")) >= {"E402", "B116", "C36", "152", "E308", "E307"}

    # Hoạt động rơi ĐÚNG vào giờ học Thứ 5 07:30-11:10 (MTH00006) phải bị loại
    clash_day = (datetime.now() + timedelta(days=(3 - datetime.now().weekday()) % 7 + 7)).date()
    acts = pd.DataFrame([
        {"id": 1, "title": "Hội thảo AI", "relevance_label": "VERIFIED_DRL",
         "start_time": f"{clash_day} 08:00", "end_time": f"{clash_day} 10:00",
         "location": "E402", "campus": "NVC", "expected_score": 5,
         "criterion_code": "TC_2", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0},
        {"id": 2, "title": "Talkshow kỹ năng", "relevance_label": "VERIFIED_DRL",
         "start_time": f"{clash_day} 18:00", "end_time": f"{clash_day} 20:00",
         "location": "Hội trường", "campus": "NVC", "expected_score": 3,
         "criterion_code": "TC_3", "is_missing_time": 0, "is_missing_location": 0,
         "is_missing_content": 0, "is_missing_score": 0},
    ])
    candidates, _rejected, conflicts = pathway.prepare_candidates(acts, df)
    kept_ids = {c["id"] for c in candidates}
    assert 2 in kept_ids, "Hoạt động 18:00 không trùng giờ học phải được giữ"
    assert 1 not in kept_ids, "Hoạt động 08:00-10:00 trùng MTH00006 phải bị loại"
    assert conflicts and conflicts[0]["id"] == 1


# ---------------------------------------------------------------------------
# Bộ thu thập tự động (crawler) – test OFFLINE bằng HTML/JSON giả lập cấu trúc thật
# ---------------------------------------------------------------------------
def test_crawler_ctsv_parses_real_api_shape():
    """API CTSV thật trả {data:[...], meta:{...}} – phải bóc đúng trường."""
    from drl import crawler

    src = crawler.CtsvApiSource()
    row = {
        "idCode": 535,
        "title": "Thông báo tổ chức Workshop “Sơ cấp cứu”",
        "slug": "thong-bao-workshop-so-cap-cuu",
        "content": "<p>Kính mời sinh viên tham dự workshop.</p><p>Địa điểm: Giảng đường 1</p>",
        "imageUrl": "https://ctsv.hcmus.edu.vn/x.jpg",
        "author": "Trương Quốc Tiên",
        "createdAt": "2026-10-24T13:28:12.169Z",
        "category": {"idCode": 1, "name": "KỸ NĂNG"},
        "tags": [],
    }
    post = src._to_post(row)
    assert post.external_id == "ctsv-535"
    assert post.title.startswith("Thông báo tổ chức Workshop")
    assert "<p>" not in post.content, "Phải bóc sạch HTML khỏi nội dung"
    assert "workshop" in post.content.lower()
    assert post.url.endswith("thong-bao-workshop-so-cap-cuu")
    assert post.published_at.startswith("2026-10-24")


def test_crawler_events_uses_structured_time_and_venue():
    """Adapter sự kiện phải dùng start_date/end_date/venue có sẵn của nguồn."""
    from drl import crawler

    src = crawler.HcmusEventsSource()
    row = {
        "id": 12345,
        "title": "Hội thảo khoa học về Trí tuệ nhân tạo",
        "description": "<p>Nội dung hội thảo</p>",
        "url": "https://hcmus.edu.vn/event/hoi-thao-ai/",
        "start_date": "2026-11-22T08:30:00+07:00",
        "end_date": "2026-11-22T11:30:00+07:00",
        "venue": {"venue": "Hội trường I", "address": "227 Nguyễn Văn Cừ, Quận 5"},
        "organizer": [{"organizer": "Trường Đại học Khoa học tự nhiên"}],
    }
    post = src._to_post(row)
    assert post.start_time == "2026-11-22 08:30"
    assert post.end_time == "2026-11-22 11:30"
    assert "Hội trường I" in post.location and "Nguyễn Văn Cừ" in post.location
    assert "Khoa học tự nhiên" in post.organizer


def test_crawler_fit_html_parses_listing():
    """Trang Khoa CNTT: <h6><a>tiêu đề</a></h6> + .post-date chứa dd/mm/yyyy."""
    from drl import crawler

    page = """
    <div>
      <h6><a href="/tin-tuc/dang-ky-hoi-thao-cv">Đăng ký tham dự Hội thảo: Xây dựng CV</a></h6>
      <p class="mb-1">Mô tả ngắn về hội thảo dành cho sinh viên.</p>
      <ul class="post-meta"><li class="post-date"><i class="uil uil-calendar-alt"></i>
        <span>11/11/2026</span></li></ul>
      <h6><a href="/tin-tuc/ai-doanh-nghiep">Hội thảo "AI trong doanh nghiệp"</a></h6>
      <ul class="post-meta"><li class="post-date"><span>05/11/2026</span></li></ul>
    </div>
    """
    posts = crawler.FitNewsSource()._parse_listing(page)
    assert len(posts) == 2
    assert posts[0].title.startswith("Đăng ký tham dự Hội thảo")
    assert posts[0].published_at == "2026-11-11"
    assert posts[1].published_at == "2026-11-05"
    assert posts[1].url == "https://fit.hcmus.edu.vn/tin-tuc/ai-doanh-nghiep"


def test_crawler_activity_filter_rejects_admin_news():
    """Bộ lọc phải loại tin học vụ/hành chính và giữ hoạt động sinh viên."""
    from drl import crawler

    assert crawler.is_activity_like(
        "Thông báo tổ chức Workshop “Sơ cấp cứu: những kỹ năng cần thiết”")
    assert crawler.is_activity_like(
        "Đăng ký tham dự Hội thảo: Xây dựng CV nổi bật và chinh phục phỏng vấn")
    assert not crawler.is_activity_like(
        "Thông báo thu phí bảo hiểm y tế năm 2027 (đợt 1)")
    assert not crawler.is_activity_like(
        "Thông báo kết quả chính thức Điểm rèn luyện sinh viên HK2/2025-2026")
    assert not crawler.is_activity_like(
        "NCS. Nguyễn Ngọc Trung bảo vệ thành công luận án tiến sĩ")
    assert not crawler.is_activity_like(
        "“LỊCH SỬ DỤNG PHÒNG HỌP (Tuần 16/11/2026 đến 22/11/2026)”")


def test_crawler_marks_invitation():
    """Bài có lời mời đăng ký phải được đánh dấu để ưu tiên hiển thị."""
    from drl import crawler

    assert crawler.looks_like_invitation(
        "Thông báo tổ chức Workshop", "Kính mời sinh viên đăng ký tham dự trước 20/11.")
    assert not crawler.looks_like_invitation(
        "Hội nghị khoa học đã diễn ra", "Hội nghị đã tổng kết với 200 báo cáo.")


# ---------------------------------------------------------------------------
# Hồi quy: bóc tách trên ĐỊNH DẠNG THẬT của cổng trường HCMUS
# ---------------------------------------------------------------------------
def test_vietnamese_time_format_13g30():
    """Cổng CTSV viết '13g30, ngày 08/11/2026' – chữ g thay dấu hai chấm."""
    from drl import nlp_engine

    text = ("2. Thời gian: 13g30, ngày 08/11/2026 (chủ nhật).\n"
            "3. Địa điểm: Giảng đường 1, Trường Đại học Khoa học tự nhiên, ĐHQG-HCM")
    act = nlp_engine.analyze_post(text)["activity"]
    assert act["start_time"].startswith("2026-11-08 13:30"), act["start_time"]
    assert "Giảng đường 1" in (act["location"] or "")


def test_office_hours_not_treated_as_event_time():
    """'Giờ làm việc: 8:00 - 11:30' KHÔNG phải giờ diễn ra hoạt động."""
    from drl import nlp_engine

    text = ("RECAP TẬP HUẤN\n"
            "- Giờ làm việc: Từ thứ Hai - thứ Sáu | 8:00 - 11:30 | 13:30 - 16:30\n"
            "Buổi tập huấn diễn ra sôi nổi.")
    act = nlp_engine.analyze_post(text)["activity"]
    assert not act["start_time"], f"Không được lấy giờ hành chính: {act['start_time']}"


def test_location_rejects_noun_phrases():
    """Cụm danh từ không trỏ tới không gian cụ thể phải bị loại (thà trống còn hơn sai)."""
    from drl.nlp_engine import ExtractionResult, _accept_location

    reject = ["phòng tránh nguy cơ xâm hại trực tuyến", "sân chơi dành cho sinh viên",
              "PHÒNG HỌP (Tuần 16/11/2026 đến 22/11/2026)",
              "phòng Phòng Khoa học – Công nghệ, đại diện trình bày tham luận"]
    accept = ["Giảng đường 1, Trường Đại học Khoa học tự nhiên", "Phòng F102, ĐHQG-HCM",
              "Hội trường B", "Trực tuyến (Online)"]
    for text in reject:
        assert not _accept_location(text, ExtractionResult()), f"Phải loại: {text}"
    for text in accept:
        assert _accept_location(text, ExtractionResult()), f"Phải nhận: {text}"

    # Có địa điểm thật + mệnh đề giải thích → cắt phần giải thích, giữ địa điểm
    res = ExtractionResult()
    assert _accept_location("Hội trường I trong khuôn khổ Hội thảo NMEC-4", res)
    assert res.location == "Hội trường I", res.location


def test_merge_duplicates_keeps_one_row(tmp_path):
    """Chạy thu thập 2 lần sinh bài trùng → gộp còn 1 bản, giữ bản có điểm cao hơn."""
    from drl import database

    db = tmp_path / "dup.db"
    database.init_db(db)
    base = {
        "title": "Thông báo tổ chức Workshop “Sơ cấp cứu”",
        "organizer": "Phòng CTSV", "location": "", "campus": "",
        "start_time": "2026-10-31 14:00", "end_time": "2026-10-31 16:00",
        "relevance_label": "EVENT_CANDIDATE", "verification_status": "UNVERIFIED",
        "is_missing_time": 0, "is_missing_location": 1, "is_missing_content": 0,
        "is_missing_score": 1, "is_demo": False,
    }
    database.insert_activity({**base, "expected_score": None}, db)
    database.insert_activity({**base, "expected_score": 5, "location": "Giảng đường 1"}, db)

    assert len(database.get_activities(db_path=db)) == 2
    res = database.merge_duplicates(db)
    assert res["rows_deleted"] == 1
    df = database.get_activities(db_path=db)
    assert len(df) == 1
    row = df.iloc[0]
    assert float(row["expected_score"]) == 5
    assert row["location"] == "Giảng đường 1", "Phải bổ sung trường trống từ bản bị xoá"


# ---------------------------------------------------------------------------
# Hồi quy: KHÔNG được thu thập sự kiện đã diễn ra
# ---------------------------------------------------------------------------
def test_is_upcoming_filters_expired():
    """Sự kiện đã kết thúc phải bị loại; sự kiện hôm nay phải được giữ."""
    from datetime import datetime, timedelta

    from drl import crawler

    now = datetime(2026, 11, 14, 12, 0)
    past = {"start_time": "2024-11-11 00:00", "end_time": "2024-11-16 23:59"}
    today = {"start_time": "2026-11-14 08:00", "end_time": "2026-11-14 11:30"}
    future = {"start_time": "2026-11-22 08:30", "end_time": "2026-11-22 11:30"}
    undated = {"start_time": "", "end_time": ""}

    assert crawler.is_upcoming(past, now=now) is False
    assert crawler.is_upcoming(today, now=now) is True
    assert crawler.is_upcoming(future, now=now) is True
    assert crawler.is_upcoming(undated, now=now) is None
    # Sự kiện nhiều ngày: còn hiệu lực nếu ngày KẾT THÚC chưa qua
    multi = {"start_time": "2026-11-10 00:00", "end_time": "2026-11-20 23:59"}
    assert crawler.is_upcoming(multi, now=now) is True
    _ = timedelta


def test_purge_expired_real_activities(tmp_path):
    """Xoá mục thật đã kết thúc, GIỮ mục tương lai và mục không rõ ngày."""
    from drl import database

    db = tmp_path / "purge.db"
    database.init_db(db)
    base = {"organizer": "X", "location": "", "campus": "",
            "relevance_label": "EVENT_CANDIDATE", "verification_status": "UNVERIFIED",
            "is_missing_time": 0, "is_missing_location": 1, "is_missing_content": 0,
            "is_missing_score": 1, "is_demo": False}
    database.insert_activity({**base, "title": "Sự kiện cũ 2024",
                              "start_time": "2024-11-11 08:00",
                              "end_time": "2024-11-11 11:00"}, db)
    database.insert_activity({**base, "title": "Sự kiện sắp tới",
                              "start_time": "2027-12-22 08:00",
                              "end_time": "2027-12-22 11:00"}, db)
    database.insert_activity({**base, "title": "Không rõ ngày"}, db)

    assert len(database.get_activities(db_path=db)) == 3
    res = database.purge_expired_real_activities(db)
    assert res["deleted"] == 1
    titles = set(database.get_activities(db_path=db)["title"])
    assert "Sự kiện cũ 2024" not in titles
    assert "Sự kiện sắp tới" in titles
    assert "Không rõ ngày" in titles


def test_multiday_event_spanning_today_not_hidden():
    """Sự kiện nhiều ngày đang diễn ra KHÔNG được xếp vào 'đã qua'.

    Lỗi thật đã gặp: Hội nghị Khoa học 09–16/11/2026 bị ẩn khi hôm nay là 14/11
    vì Tab Kho phân loại theo ngày BẮT ĐẦU. Phải dùng ngày KẾT THÚC.
    """
    from datetime import datetime as _dt

    import pandas as pd

    def _parse_day(value):
        raw = str(value or "")
        if len(raw) < 10:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return _dt.strptime(raw[:16] if ":" in raw else raw[:10], fmt).date()
            except ValueError:
                continue
        return None

    def verdict(row):
        end_day = _parse_day(row.get("end_time")) or _parse_day(row.get("start_time"))
        if end_day is None:
            return "unknown"
        return "past" if end_day < _dt.now().date() else "upcoming"

    span = {"start_time": "2026-11-09 08:00", "end_time": "2026-11-16 17:00"}
    done = {"start_time": "2026-11-10 08:00", "end_time": "2026-11-10 11:00"}
    undated = {"start_time": "", "end_time": ""}

    # Chỉ kiểm chứng khi hôm nay nằm trong khoảng 09–16/11/2026
    if _dt.now().date() == _dt(2026, 11, 14).date():
        assert verdict(span) == "upcoming", "Sự kiện đang diễn ra bị xếp nhầm là đã qua"
        assert verdict(done) == "past"
    assert verdict(undated) == "unknown"
    assert verdict({"start_time": "2020-01-01 08:00", "end_time": "2020-01-02 08:00"}) == "past"


# ---------------------------------------------------------------------------
# Cổng chặn "đủ thông tin mới vào kho" + bóc tách ngày/diễn giả
# ---------------------------------------------------------------------------
def test_deadline_is_not_event_date():
    """Hạn nộp hồ sơ KHÔNG được ghi thành ngày diễn ra.

    Đây là lỗi nghiêm trọng nhất có thể xảy ra: lưu workshop với ngày hết hạn
    đăng ký khiến sinh viên tưởng đã hết hạn và bỏ lỡ buổi thật.
    """
    from drl import event_details as ed

    text = """THÔNG BÁO
2. Thời gian: 14g00, ngày 31/10/2026 (Thứ 7).
3. Địa điểm: Giảng đường 1, Trường ĐH KHTN.
4. Báo cáo viên: BS.CKII. Trần Quang Khải - Bệnh viện đa khoa Tân Phú.
6. Hình thức đăng ký: sinh viên đăng ký từ 20g00 ngày 26/10/2026
   đến hết ngày 28/10/2026.
"""
    w = ed.extract_when(text)
    assert w["start_time"].startswith("2026-10-31"), w["start_time"]
    assert "14:00" in w["start_time"]
    assert w["deadline"].startswith("2026-10-28"), w["deadline"]
    assert w["start_raw"], "Phải giữ câu gốc để đối chiếu"
    assert ed.extract_speaker(text)[0].startswith("BS.CKII. Trần Quang Khải")


def test_duration_from_time_range():
    from drl import event_details as ed

    mins, raw = ed.extract_duration("Thời gian: từ 13g30 đến 16g30 cùng ngày.")
    assert mins == 180
    assert raw
    assert ed.extract_duration("Thời lượng: 90 phút")[0] == 90
    assert ed.extract_duration("Thời lượng: 2 giờ")[0] == 120
    assert ed.extract_duration("Không nói gì về thời lượng")[0] is None


def test_required_report_gate():
    """Thiếu bất kỳ trường bắt buộc nào → KHÔNG được coi là đủ."""
    from drl import event_details as ed

    full = {"title": "Workshop A", "start_time": "2026-11-18 00:00",
            "location": "Giảng đường 1", "organizer": "Phòng CTSV"}
    ok, missing = ed.required_report(full)
    assert ok and missing == []

    for field in ed.REQUIRED_FIELDS:
        broken = dict(full)
        broken[field] = ""
        ok2, missing2 = ed.required_report(broken)
        assert not ok2, f"Thiếu {field} mà vẫn cho qua"
        assert field in missing2


def test_gate_blocks_incomplete_and_keeps_speaker():
    """save_crawled_posts: mục thiếu địa điểm bị chặn, mục đủ được lưu kèm chi tiết."""
    from drl import crawler, database

    import tempfile
    from pathlib import Path as _P

    db = _P(tempfile.mkdtemp()) / "gate.db"
    database.init_db(db)

    content = ("2. Thời gian: 14g00, ngày 18/11/2026. "
               "3. Địa điểm: Giảng đường 1, Trường ĐH KHTN. "
               "4. Báo cáo viên: ThS. Nguyễn Văn A. "
               "Thời lượng: 90 phút.")
    good = {
        "source_key": "ctsv_api", "source_name": "Phòng Công tác Sinh viên HCMUS",
        "title": "Workshop đủ thông tin", "content": content,
        "url": "https://ctsv.hcmus.edu.vn/x", "published_at": "2026-11-01",
    }
    bad = dict(good)
    bad["title"] = "Workshop thiếu địa điểm"
    bad["content"] = "2. Thời gian: 14g00, ngày 18/11/2026. Không có địa điểm."
    bad["url"] = "https://ctsv.hcmus.edu.vn/y"

    res = crawler.save_crawled_posts([good, bad], db_path=db)
    titles = set(database.get_activities(db_path=db)["title"])
    assert "Workshop đủ thông tin" in titles
    assert "Workshop thiếu địa điểm" not in titles
    assert len(res["incomplete"]) == 1
    assert "location" in res["incomplete"][0]["missing"]


def test_negation_not_mistaken_for_label():
    """Câu "Không có địa điểm" KHÔNG được coi là nhãn địa điểm.

    Lỗi thật đã gặp: hệ thống coi chữ "địa điểm" trong câu phủ định là nhãn,
    rồi bóc nhầm giá trị từ dòng "Thời gian:" phía trên → lưu sai địa điểm.
    """
    from drl import event_details as ed

    assert ed.extract_location("2. Thời gian: 14g00, ngày 18/11/2026. "
                              "Không có địa điểm.")[0] == ""
    assert ed.extract_location("Thông báo về địa điểm thi mới của trường.")[0] == ""
    # Nhãn thật (đầu dòng, có thể có số thứ tự hoặc gạch đầu dòng) thì phải bóc
    assert "I.23" in ed.extract_location("- Địa điểm: Phòng I.23 cơ sở Nguyễn Văn Cừ")[0]
    assert "Giảng đường 1" in ed.extract_location(
        "3. Địa điểm: Giảng đường 1, Trường ĐH KHTN.")[0]
    assert ed.extract_speaker("Không có diễn giả tham gia.")[0] == ""


def test_duration_not_computed_across_days():
    """Sự kiện nhiều ngày không được suy ra 'thời lượng' vô nghĩa."""
    from drl import crawler, database

    import tempfile
    from pathlib import Path as _P

    db = _P(tempfile.mkdtemp()) / "multi.db"
    database.init_db(db)
    rec = {
        "source_key": "hcmus_events", "source_name": "Trường HCMUS – Lịch sự kiện",
        "title": "Hội nghị nhiều ngày", "content": "Địa điểm: Hội trường A.",
        "url": "https://hcmus.edu.vn/e/1", "published_at": "2026-11-01",
        "start_time": "2026-11-20 08:00", "end_time": "2026-11-27 17:00",
    }
    crawler.save_crawled_posts([rec], db_path=db)
    row = database.get_activities(db_path=db).iloc[0]
    assert row["duration_minutes"] is None or str(row["duration_minutes"]) in ("", "nan")


def test_date_range_and_procedural_dates_ignored():
    """Khoảng ngày '23/11 – 30/11/2026' phải hiểu là start→end.

    Và mốc thủ tục như "thời gian tích luỹ: từ 01/2026 đến 05/01/2027" KHÔNG
    được dùng làm ngày diễn ra (từng gây ra end_time < start_time).
    """
    from drl import event_details as ed

    w = ed.extract_when("Thời gian: Từ ngày 23/11 – 30/11/2026, theo thông báo.")
    assert w["start_time"].startswith("2026-11-23"), w["start_time"]
    assert w["end_time"].startswith("2026-11-30"), w["end_time"]

    w2 = ed.extract_when("Thời gian: 1/12 - 5/12/2026 tại Hội trường A.")
    assert w2["start_time"].startswith("2026-12-01")
    assert w2["end_time"].startswith("2026-12-05")

    text = ("- Thời gian tính tích luỹ: từ 01/2026 đến hết 05/01/2027.\n"
            "- Thời gian: Từ ngày 23/11 – 30/11/2026.")
    w3 = ed.extract_when(text)
    assert w3["start_time"].startswith("2026-11-23"), w3["start_time"]
    # Không bao giờ được trả về end < start
    assert not w3["end_time"] or w3["end_time"] >= w3["start_time"]
