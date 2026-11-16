"""Dữ liệu [DEMO] khởi tạo sẵn + tập dữ liệu Benchmark cho module ML.

TẤT CẢ dữ liệu trong file này đều mang nhãn [DEMO]:
- Thời khóa biểu mẫu theo định dạng CTĐB HCMUS (không phải lịch thật của bất kỳ
  sinh viên nào).
- Bộ tiêu chí ĐRL mẫu theo cấu trúc quy chế; điểm tối đa là số minh hoạ, phải
  đối chiếu với quy chế chính thức trên hcmus.drl.vn trước khi dùng thật.
- 8+ bài đăng mẫu mô phỏng văn phong fanpage OSA HCMUS, gồm đủ các tình huống:
  đủ thông tin, thiếu địa điểm, thiếu thời gian, nhắc hạn đăng ký, quảng bá
  không liên quan.
- Tập Benchmark 28 mẫu đã gán nhãn chuẩn (ground truth) phục vụ Tab 6.
"""
from __future__ import annotations

from typing import Optional

from . import config, database, nlp_engine

DEMO = config.DEMO_TAG

# ---------------------------------------------------------------------------
# 1. Bộ tiêu chí ĐRL [DEMO] – tổng 100 điểm
# ---------------------------------------------------------------------------
DEMO_CRITERIA = [
    {
        "code": "TC_1.1",
        "name": "Ý thức và kết quả học tập",
        "category": "I. Ý thức học tập",
        "max_score": 20,
        "mandatory": True,
        "evidence_required": "Bảng điểm / xác nhận của Khoa",
        "rule_reference": f"{DEMO} Mục I.1 – Ý thức và kết quả học tập (tối đa 20đ). Cần đối chiếu quy chế chính thức hcmus.drl.vn.",
    },
    {
        "code": "TC_2.1",
        "name": "Hoạt động học thuật, nghiên cứu khoa học",
        "category": "II. Hoạt động học thuật",
        "max_score": 15,
        "mandatory": False,
        "evidence_required": "Giấy chứng nhận / danh sách điểm danh của đơn vị tổ chức",
        "rule_reference": f"{DEMO} Mục II.1 – Tham gia hội thảo học thuật cấp Khoa/Trường (tối đa 15đ).",
    },
    {
        "code": "TC_3.1",
        "name": "Hoạt động chính trị, xã hội, tình nguyện",
        "category": "III. Hoạt động chính trị – xã hội",
        "max_score": 20,
        "mandatory": False,
        "evidence_required": "Xác nhận của Đoàn – Hội / đơn vị tổ chức chiến dịch",
        "rule_reference": f"{DEMO} Mục III.1 – Chiến dịch tình nguyện, hoạt động chính trị xã hội (tối đa 20đ).",
    },
    {
        "code": "TC_3.2",
        "name": "Hiến máu nhân đạo và hoạt động vì cộng đồng",
        "category": "III. Hoạt động chính trị – xã hội",
        "max_score": 5,
        "mandatory": False,
        "evidence_required": "Giấy chứng nhận hiến máu / xác nhận của Bệnh viện",
        "rule_reference": f"{DEMO} Mục III.2 – Hiến máu nhân đạo (tối đa 5đ).",
    },
    {
        "code": "TC_4.1",
        "name": "Hoạt động văn hóa, văn nghệ",
        "category": "IV. Văn hóa – Thể thao",
        "max_score": 5,
        "mandatory": False,
        "evidence_required": "Xác nhận tham gia của Ban tổ chức",
        "rule_reference": f"{DEMO} Mục IV.1 – Hoạt động văn hóa, văn nghệ (tối đa 5đ).",
    },
    {
        "code": "TC_4.2",
        "name": "Hoạt động thể dục thể thao",
        "category": "IV. Văn hóa – Thể thao",
        "max_score": 5,
        "mandatory": False,
        "evidence_required": "Xác nhận tham gia giải đấu / CLB thể thao",
        "rule_reference": f"{DEMO} Mục IV.2 – Hoạt động thể dục thể thao (tối đa 5đ).",
    },
    {
        "code": "TC_5.1",
        "name": "Hoạt động hội nhập, kỹ năng, ngoại ngữ",
        "category": "V. Hội nhập – Kỹ năng",
        "max_score": 10,
        "mandatory": False,
        "evidence_required": "Chứng nhận hoàn thành workshop / khoá kỹ năng",
        "rule_reference": f"{DEMO} Mục V.1 – Kỹ năng mềm, ngoại ngữ, hội nhập (tối đa 10đ).",
    },
    {
        "code": "TC_5.2",
        "name": "Khởi nghiệp, đổi mới sáng tạo",
        "category": "V. Hội nhập – Kỹ năng",
        "max_score": 5,
        "mandatory": False,
        "evidence_required": "Giấy chứng nhận cuộc thi / xác nhận của Ban tổ chức",
        "rule_reference": f"{DEMO} Mục V.2 – Khởi nghiệp, đổi mới sáng tạo (tối đa 5đ).",
    },
    {
        "code": "TC_6.1",
        "name": "Ý thức chấp hành nội quy, quy định, pháp luật",
        "category": "VI. Ý thức công dân",
        "max_score": 10,
        "mandatory": True,
        "evidence_required": "Xác nhận của Cố vấn học tập / Phòng CTSV",
        "rule_reference": f"{DEMO} Mục VI.1 – Chấp hành nội quy, pháp luật (tối đa 10đ).",
    },
    {
        "code": "TC_6.2",
        "name": "Hoạt động cộng đồng, ký túc xá",
        "category": "VI. Ý thức công dân",
        "max_score": 5,
        "mandatory": False,
        "evidence_required": "Xác nhận của Ban quản lý KTX / Ban điều hành khu phố",
        "rule_reference": f"{DEMO} Mục VI.2 – Hoạt động cộng đồng, KTX (tối đa 5đ).",
    },
]

# ---------------------------------------------------------------------------
# 2. Thời khóa biểu [DEMO] – đúng khung dữ liệu CTĐB (portal.ctdb.hcmus.edu.vn)
# ---------------------------------------------------------------------------
DEMO_SCHEDULE = [
    {"course_code": "CSC10002", "course_name": f"{DEMO} Kỹ thuật lập trình",
     "day_of_week": "Monday", "start_time": "07:30", "end_time": "11:30",
     "room": "E302", "campus": "NVC"},
    {"course_code": "MTH00003", "course_name": f"{DEMO} Đại số tuyến tính",
     "day_of_week": "Wednesday", "start_time": "13:30", "end_time": "17:00",
     "room": "F204", "campus": "Linh Trung"},
    {"course_code": "PHY00001", "course_name": f"{DEMO} Vật lý đại cương",
     "day_of_week": "Thursday", "start_time": "07:30", "end_time": "11:30",
     "room": "A205", "campus": "Linh Trung"},
    {"course_code": "ENG10001", "course_name": f"{DEMO} Anh văn giao tiếp",
     "day_of_week": "Friday", "start_time": "13:30", "end_time": "15:30",
     "room": "C101", "campus": "NVC"},
]

# ---------------------------------------------------------------------------
# 3. Hồ sơ sinh viên [DEMO]
# ---------------------------------------------------------------------------
DEMO_STUDENT_ID = "25127302"

DEMO_PROGRESS = [
    {"criterion_code": "TC_1.1", "current_score": 18},
    {"criterion_code": "TC_2.1", "current_score": 5},
    {"criterion_code": "TC_3.1", "current_score": 10},
    {"criterion_code": "TC_3.2", "current_score": 4},
    {"criterion_code": "TC_4.1", "current_score": 3},
    {"criterion_code": "TC_4.2", "current_score": 3},
    {"criterion_code": "TC_5.1", "current_score": 6},
    {"criterion_code": "TC_5.2", "current_score": 2},
    {"criterion_code": "TC_6.1", "current_score": 10},
    {"criterion_code": "TC_6.2", "current_score": 0},
]

# ---------------------------------------------------------------------------
# 4. Bài đăng OSA HCMUS [DEMO]
# ---------------------------------------------------------------------------
DEMO_POSTS = [
    {
        "key": "hoi_thao_ai",
        "fetch_method": "DEMO_SEED",
        "text": f"""📣 {DEMO} THÔNG BÁO: HỘI THẢO "KỸ NĂNG NGHIÊN CỨU KHOA HỌC & ỨNG DỤNG AI 2026"

Đơn vị tổ chức: Đoàn Khoa Công nghệ Thông tin - Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM
Mời các bạn sinh viên tham gia Hội thảo "Kỹ năng Nghiên cứu Khoa học & Ứng dụng AI 2026" với sự chia sẻ của các giảng viên và cựu sinh viên.

⏰ Thời gian: 08h30 - 11h30, ngày 22/11/2026
📍 Địa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ, Q.5
🎁 Sinh viên tham gia đầy đủ được cộng 5 điểm rèn luyện (hoạt động học thuật).
👉 Đăng ký trước 23h59 ngày 20/11/2026 tại: https://forms.gle/demo-hoithao-ai
#OSAHCMUS #HCMUS #HoiThao""",
    },
    {
        "key": "xuan_tinh_nguyen",
        "fetch_method": "DEMO_SEED",
        "text": f"""🌱 {DEMO} CHIẾN DỊCH XUÂN TÌNH NGUYỆN 2027 – ĐĂNG KÝ NGAY!

Đoàn Trường Đại học Khoa học Tự nhiên mời các bạn sinh viên đăng ký tham gia Chiến dịch Xuân tình nguyện 2027, đồng hành cùng các hoạt động vì cộng đồng tại các xã vùng ven TP.HCM.

⏰ Thời gian: 08h00 ngày 10/01/2027 (tập trung và di chuyển theo đoàn)
👉 Đăng ký trước 17h00 ngày 05/01/2027 tại: https://forms.gle/demo-xuantinhnguyen
🎁 Tham gia đầy đủ được cộng 10 điểm rèn luyện (hoạt động chính trị - xã hội).
#XuanTinhNguyen #HCMUS""",
    },
    {
        "key": "workshop_thuyet_trinh",
        "fetch_method": "DEMO_SEED",
        "text": f"""💡 {DEMO} WORKSHOP "KỸ NĂNG THUYẾT TRÌNH TỰ TIN" – ĐOÀN KHOA VẬT LÝ

Đoàn Khoa Vật lý - Vật lý Kỹ thuật tổ chức workshop Kỹ năng thuyết trình tự tin dành cho sinh viên, hướng dẫn bởi chuyên gia kỹ năng mềm.

📍 Địa điểm: Phòng F102, Cơ sở Linh Trung
👉 Đăng ký tại: https://forms.gle/demo-workshop-thuyettrinh
🎁 Sinh viên tham gia được cộng 3 điểm rèn luyện.
#Workshop #KyNangMem #HCMUS""",
    },
    {
        "key": "nhac_han_ai",
        "fetch_method": "DEMO_SEED",
        "text": f"""⏰ {DEMO} NHẮC HẠN: HỘI THẢO "KỸ NĂNG NGHIÊN CỨU KHOA HỌC & ỨNG DỤNG AI 2026"

Các bạn ơi, hạn chót đăng ký Hội thảo Kỹ năng Nghiên cứu Khoa học & Ứng dụng AI 2026 là 23h59 ngày 20/11/2026. Đừng quên nhé!

📍 Địa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ, Q.5
👉 Link đăng ký: https://forms.gle/demo-hoithao-ai
🎁 Tham gia đầy đủ được cộng 5 điểm rèn luyện.
#NhacHan #HCMUS""",
    },
    {
        "key": "cuoc_thi_khoi_nghiep",
        "fetch_method": "DEMO_SEED",
        "text": f"""🚀 {DEMO} CUỘC THI "Ý TƯỞNG KHỞI NGHIỆP SINH VIÊN HCMUS 2027"

Trung tâm Đổi mới sáng tạo phối hợp Đoàn Trường tổ chức Cuộc thi Ý tưởng Khởi nghiệp Sinh viên HCMUS 2027. Cuộc thi dành cho sinh viên có ý tưởng/dự án khởi nghiệp, đổi mới sáng tạo.

⏰ Vòng chung kết: 13h30 - 17h00 ngày 05/12/2026
📍 Địa điểm: Hội trường II, Cơ sở Linh Trung
👉 Đăng ký trước 22h00 ngày 01/12/2026 tại: https://forms.gle/demo-khoinghiep
#KhoiNghiep #HCMUS #SinhVien""",
    },
    {
        "key": "seminar_chu_nhat",
        "fetch_method": "DEMO_SEED",
        "text": f"""📚 {DEMO} SEMINAR "ỨNG DỤNG TOÁN HỌC TRONG TRÍ TUỆ NHÂN TẠO" - ĐOÀN KHOA TOÁN - TIN HỌC

Đoàn Khoa Toán - Tin học tổ chức seminar học thuật dành cho sinh viên quan tâm đến Toán ứng dụng và Trí tuệ nhân tạo.

⏰ Thời gian: 14h00 - 16h00, ngày 21/11/2026
📍 Địa điểm: Phòng B.204, Cơ sở Nguyễn Văn Cừ, Q.5
🎁 Sinh viên tham gia đầy đủ được cộng 3 điểm rèn luyện (hoạt động học thuật).
👉 Đăng ký trước 20h00 ngày 19/11/2026 tại: https://forms.gle/demo-seminar-toan
#Seminar #ToanUngDung #HCMUS""",
    },
    {
        "key": "tap_huan_thu_nam",
        "fetch_method": "DEMO_SEED",
        "text": f"""🧑‍🏫 {DEMO} LỚP TẬP HUẤN KỸ NĂNG MỀM "GIAO TIẾP & LÀM VIỆC NHÓM" - ĐOÀN KHOA HÓA

Đoàn Khoa Hóa học tổ chức lớp tập huấn kỹ năng mềm dành cho sinh viên năm 1-2.

⏰ Thời gian: 08h00 - 11h00, ngày 26/11/2026 (Thứ Năm)
📍 Địa điểm: Phòng B105, Cơ sở Linh Trung, Thủ Đức
🎁 Sinh viên tham gia đầy đủ được cộng 3 điểm rèn luyện (hoạt động kỹ năng).
👉 Đăng ký trước 23h59 ngày 24/11/2026 tại: https://forms.gle/demo-taphuan
#KyNangMem #TapHuan #HCMUS""",
    },
    {
        "key": "chuc_mung_olympic",
        "fetch_method": "DEMO_SEED",
        "text": f"""🎉 {DEMO} CHÚC MỪNG ĐỘI TUYỂN OLYMPIC TIN HỌC HCMUS

Trường Đại học Khoa học Tự nhiên chúc mừng đội tuyển Olympic Tin học đạt thành tích xuất sắc tại Kỳ thi Olympic Tin học sinh viên toàn quốc. Chúc mừng năm mới Quý thầy cô và các bạn sinh viên! 🎊
#ChucMung #OlympicTinHoc #HCMUS""",
    },
    {
        "key": "tuyen_thuc_tap",
        "fetch_method": "DEMO_SEED",
        "text": f"""💼 {DEMO} TUYỂN THỰC TẬP SINH – CÔNG TY XYZ SOFTWARE

Công ty XYZ Software tuyển thực tập sinh Backend, làm việc tại văn phòng Quận 1. Ứng viên là sinh viên năm 3-4, có ưu đãi lương 8-12 triệu/tháng, được đào tạo và hỗ trợ việc làm.
Nộp CV tại: https://demo-company.example/jobs
#TuyenDung #ThucTap #IT""",
    },
    {
        "key": "hien_mau",
        "fetch_method": "DEMO_SEED",
        "text": f"""❤️ {DEMO} NGÀY HỘI HIẾN MÁU NHÂN ĐẠO – "GIỌT HỒNG HCMUS 2026"

Đoàn Trường phối hợp Bệnh viện Truyền máu Huyết học tổ chức Ngày hội Hiến máu nhân đạo dành cho sinh viên.

⏰ Thời gian: 07h30 - 10h00, ngày 28/11/2026
📍 Địa điểm: Sân Trường, Cơ sở Nguyễn Văn Cừ, Q.5
🎁 Sinh viên tham gia hiến máu được cộng 4 điểm rèn luyện (hoạt động vì cộng đồng).
👉 Đăng ký trước 20h00 ngày 26/11/2026 tại: https://forms.gle/demo-hienmau
#HienMau #HCMUS""",
    },
    {
        "key": "ngay_hoi_clb",
        "fetch_method": "DEMO_SEED",
        "text": f"""🎪 {DEMO} NGÀY HỘI CÂU LẠC BỘ KHOA HỌC & CÔNG NGHỆ HCMUS 2026

Trung tâm Hỗ trợ Sinh viên tổ chức Ngày hội Câu lạc bộ Khoa học & Công nghệ, quy tụ hơn 20 câu lạc bộ học thuật của trường. Sinh viên tham gia trải nghiệm, giao lưu và đăng ký thành viên CLB.

⏰ Thời gian: 11h00 - 12h30, ngày 28/11/2026
📍 Địa điểm: Sân C, Cơ sở Linh Trung, Thủ Đức
🎁 Sinh viên tham gia đầy đủ được cộng 5 điểm rèn luyện (hoạt động học thuật).
👉 Đăng ký trước 23h59 ngày 25/11/2026 tại: https://forms.gle/demo-ngayhoiclB
#NgayHoiCLB #HCMUS""",
    },
]

# Trạng thái gán sẵn cho từng bài demo (chỉ áp dụng sau khi phân tích)
DEMO_POST_STATE = {
    "hoi_thao_ai": {"verified": False},
    "xuan_tinh_nguyen": {"verified": False},
    "workshop_thuyet_trinh": {"verified": False},
    "nhac_han_ai": {"verified": False, "link_parent": "hoi_thao_ai"},
    "cuoc_thi_khoi_nghiep": {"verified": False},
    "chuc_mung_olympic": {"verified": False},
    "tuyen_thuc_tap": {"verified": False},
    "hien_mau": {"verified": False},
    "seminar_chu_nhat": {"verified": False},
    "tap_huan_thu_nam": {"verified": False},
    # Bài này được gán sẵn VERIFIED_DRL nhưng ghi rõ trong ai_explanation là
    # dữ liệu DEMO – KHÔNG phải xác minh thật từ OSA HCMUS.
    "ngay_hoi_clb": {
        "verified": True,
        "verified_note": (
            f"{DEMO} Hoạt động này được gán sẵn trạng thái VERIFIED_DRL để minh hoạ "
            "luồng 'Điểm đã xác minh' trên Dashboard. Đây KHÔNG phải xác minh thật "
            "từ đơn vị tổ chức hay hcmus.drl.vn."
        ),
    },
}

# ---------------------------------------------------------------------------
# 5. Bộ dữ liệu Benchmark (ground truth) cho module ML – 28 mẫu
# ---------------------------------------------------------------------------
BENCHMARK_DATASET = [
    # ---------------- NOT_RELEVANT (7) ----------------
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} CHÚC MỪNG NĂM MỚI 2027! Ban Chấp hành Đoàn Trường kính chúc Quý thầy cô và các bạn sinh viên một năm mới an khang thịnh vượng, vạn sự như ý. Hẹn gặp lại các bạn trong học kỳ mới!"},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} TUYỂN DỤNG THỰC TẬP SINH JAVA DEVELOPER. Công ty công nghệ tại Quận 3 tuyển thực tập sinh Java, lương 10 triệu/tháng, hỗ trợ dấu thực tập. Gửi CV về email tuyendung@demo.vn. Ưu tiên ứng viên có GPA từ 3.0."},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} THÔNG BÁO LỊCH NGHỈ TẾT DƯƠNG LỊCH. Sinh viên toàn trường được nghỉ từ ngày 01/01/2027 đến hết ngày 03/01/2027. Các lớp học phần sẽ bắt đầu lại từ ngày 04/01/2027 theo thời khóa biểu CTĐB. Trân trọng thông báo."},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} GIẢM GIÁ 50% GÓI HỌC TIẾNG ANH IELTS ONLINE. Trung tâm ngoại ngữ ưu đãi học phí 50% cho sinh viên HCMUS khi đăng ký trước 30/11/2026. Cam kết đầu ra 6.5 IELTS. Đăng ký ngay hôm nay để nhận ưu đãi giới hạn!"},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} CHÚC MỪNG ĐỘI TUYỂN ROBOTICS HCMUS ĐẠT GIẢI NHÌ CUỘC THI ROBOTCON. Nhà trường biểu dương thành tích của đội tuyển, cảm ơn quý thầy cô đã hướng dẫn và đồng hành cùng các bạn sinh viên trong suốt quá trình thi đấu."},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} THÔNG BÁO ĐÓNG HỌC PHÍ HỌC KỲ 1 NĂM HỌC 2026-2027. Sinh viên kiểm tra công nợ học phí trên cổng Portal CTĐB và hoàn tất thanh toán trước ngày 30/11/2026 để không bị khoá tài khoản đăng ký môn học. Mọi thắc mắc liên hệ Phòng Kế hoạch – Tài chính."},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} CHIA SẺ CỦA CỰU SINH VIÊN: HÀNH TRÌNH TỪ HCMUS ĐẾN HỌC BỔNG TIẾN SĨ. Cùng lắng nghe câu chuyện truyền cảm hứng của anh N.T.A, cựu sinh viên Khoa Toán - Tin học. Nội dung được đăng tải nhằm lan toả tinh thần học tập, không có hoạt động đăng ký nào kèm theo."},

    # ---------------- INSUFFICIENT_INFO (7) ----------------
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} ĐOÀN KHOA HÓA HỌC TỔ CHỨC BUỔI SINH HOẠT CHUYÊN ĐỀ VỀ KỸ NĂNG PHÒNG CHÁY CHỮA CHÁY. Sinh viên quan tâm đăng ký tham gia bằng cách điền form. Thời gian và địa điểm tổ chức sẽ được thông báo sau trong bài đăng tiếp theo."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} MỜI CÁC BẠN SINH VIÊN THAM GIA BUỔI TƯ VẤN HƯỚNG NGHIỆP CÙNG CHUYÊN GIA. Thời gian: 14h00 ngày 02/12/2026. Sinh viên đăng ký tham gia để được giải đáp thắc mắc về lộ trình nghề nghiệp. Danh sách đăng ký sẽ chốt trước buổi tư vấn."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} CUỘC THI THIẾT KẾ POSTER TUYÊN TRUYỀN AN TOÀN GIAO THÔNG. Cuộc thi dành cho sinh viên, sản phẩm nộp bằng file thiết kế. Địa điểm: Phòng truyền thống, Cơ sở Nguyễn Văn Cừ. Kết quả sẽ được công bố sau khi chấm xong."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} CHƯƠNG TRÌNH TRẢI NGHIỆM THỰC TẾ TẠI DOANH NGHIỆP DÀNH CHO SINH VIÊN. Sinh viên đăng ký tham gia chuyến đi trải nghiệm môi trường làm việc thực tế. Thời gian dự kiến trong tháng 12, địa điểm tập trung và lịch trình chi tiết sẽ cập nhật sau."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} HỘI THẢO PHƯƠNG PHÁP HỌC TẠI ĐẠI HỌC HIỆU QUẢ - ĐOÀN KHOA SINH HỌC. Thời gian: 09h00 - 11h00 ngày 08/12/2026. Địa điểm: Giảng đường B203, Cơ sở Linh Trung. Sinh viên tham gia vui lòng có mặt đúng giờ, mang theo thẻ sinh viên. Buổi hội thảo được cộng điểm rèn luyện theo quy chế hiện hành của trường."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} LỚP TẬP HUẤN KỸ NĂNG LÀM VIỆC NHÓM CHO SINH VIÊN NĂM NHẤT. Đơn vị tổ chức: Đoàn Khoa Môi trường. Địa điểm: Phòng C305, Cơ sở Nguyễn Văn Cừ. Lớp tập huấn hoàn toàn miễn phí, số lượng giới hạn, ưu tiên đăng ký sớm."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} NGÀY CHỦ NHẬT XANH - RA QUÂN DỌN VỆ SINH KHU PHỐ DO ĐOÀN TRƯỜNG PHÁT ĐỘNG. Thời gian: 07h00 ngày 29/11/2026. Sinh viên có thể đăng ký tham gia cùng địa phương, buổi ra quân có cộng điểm rèn luyện theo quy chế."},

    # ---------------- EVENT_CANDIDATE (7) ----------------
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} SEMINAR CÔNG NGHỆ BLOCKCHAIN & WEB3 - ĐOÀN KHOA CNTT.\nThời gian: 09h00 - 11h30, ngày 04/12/2026.\nĐịa điểm: Hội trường II, Cơ sở Nguyễn Văn Cừ.\nĐăng ký trước 23h59 ngày 02/12/2026 tại link trong bio. Sinh viên tham gia được điểm danh và nhận chứng nhận tham dự."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} CHUYẾN THAM QUAN DOANH NGHIỆP TẠI KHU CÔNG NGHỆ CAO.\nThời gian: 07h30 - 16h30, ngày 12/12/2026 (di chuyển bằng xe của trường).\nĐịa điểm tập trung: Cổng chính Cơ sở Linh Trung.\nĐăng ký trước 20h00 ngày 08/12/2026. Chi phí do nhà trường tài trợ, chỉ tiêu 40 sinh viên."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} GIẢI BÓNG ĐÁ SINH VIÊN TRANH CÚP HCMUS OPEN 2026.\nThời gian: 15h00 - 18h00, ngày 06/12/2026.\nĐịa điểm: Sân bóng đá Cơ sở Linh Trung.\nCác đội đăng ký trước 23h59 ngày 03/12/2026, lệ phí giải đấu do Ban tổ chức thông báo khi nhận đăng ký."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} CUỘC THI HÙNG BIỆN TIẾNG ANH - SPEAK UP 2026.\nThời gian: 13h00 - 17h00, ngày 13/12/2026.\nĐịa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ.\nVòng sơ loại nhận video dự thi trước 05/12/2026. Sinh viên quan tâm đăng ký theo đường link trong bài viết."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} NGÀY HỘI VIỆC LÀM HCMUS CAREER FAIR 2026.\nThời gian: 08h00 - 16h00, ngày 10/12/2026.\nĐịa điểm: Nhà thi đấu Cơ sở Linh Trung.\nSinh viên mang theo CV để tham gia phỏng vấn trực tiếp cùng hơn 50 doanh nghiệp. Đăng ký tại cổng thông tin việc làm của trường trước ngày 08/12/2026."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} BUỔI CHIA SẺ KINH NGHIỆM HỌC BỔNG TRAO ĐỔI SINH VIÊN QUỐC TẾ.\nThời gian: 18h00 - 20h00, ngày 03/12/2026.\nĐịa điểm: Phòng A.102, Cơ sở Nguyễn Văn Cừ.\nDiễn giả là các cựu sinh viên từng nhận học bổng trao đổi. Đăng ký trước 12h00 ngày 02/12/2026 để nhận tài liệu."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} WORKSHOP PHÁT TRIỂN BẢN THÂN VỚI MÔ HÌNH GROW.\nThời gian: 08h30 - 11h00, ngày 05/12/2026.\nĐịa điểm: Phòng B201, Cơ sở Linh Trung.\nGiới hạn 60 sinh viên, đăng ký trước 23h59 ngày 03/12/2026. Học viên tham gia đầy đủ nhận chứng nhận từ đơn vị tổ chức."},

    # ---------------- POTENTIAL_DRL (7) ----------------
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} TỌA ĐÀM \"SINH VIÊN VỚI NGHIÊN CỨU KHOA HỌC\" - ĐOÀN KHOA TOÁN - TIN HỌC.\nThời gian: 08h30 - 11h00, ngày 19/12/2026.\nĐịa điểm: Hội trường III, Cơ sở Nguyễn Văn Cừ.\nSinh viên tham gia đầy đủ được cộng 5 điểm rèn luyện cho hoạt động học thuật.\nĐăng ký trước 23h59 ngày 17/12/2026."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} CHIẾN DỊCH HIẾN MÁU NHÂN ĐẠO ĐỢT 2 - GIỌT HỒNG MÙA XUÂN.\nThời gian: 07h00 - 11h00, ngày 11/01/2027.\nĐịa điểm: Sân Trường, Cơ sở Nguyễn Văn Cừ.\nSinh viên tham gia hiến máu được cộng 4 điểm rèn luyện.\nĐăng ký trước 17h00 ngày 09/01/2027 tại văn phòng Đoàn Trường."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} NGÀY HỘI TÌNH NGUYỆN \"MÙA XUÂN CHO EM\" - ĐOÀN TRƯỜNG.\nThời gian: 08h00 - 16h00, ngày 17/01/2027.\nĐịa điểm: Trung tâm công tác xã hội huyện Bình Chánh.\nSinh viên tham gia được cộng 6 điểm rèn luyện (hoạt động chính trị - xã hội).\nĐăng ký trước 23h59 ngày 12/01/2027, chỉ tiêu 50 sinh viên."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} WORKSHOP KỸ NĂNG GIAO TIẾP VÀ THUYẾT TRÌNH TRƯỚC ĐÁM ĐÔNG.\nThời gian: 13h30 - 17h00, ngày 20/12/2026.\nĐịa điểm: Phòng D401, Cơ sở Linh Trung.\nSinh viên tham gia đầy đủ được cộng 3 điểm rèn luyện cho hoạt động kỹ năng.\nĐăng ký trước 23h59 ngày 18/12/2026."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} CUỘC THI THIẾT KẾ ỨNG DỤNG DI ĐỘNG HCMUS APP CONTEST 2026.\nThời gian: 08h00 - 12h00, ngày 26/12/2026 (vòng chung kết).\nĐịa điểm: Hội trường II, Cơ sở Nguyễn Văn Cừ.\nThí sinh tham gia vòng chung kết được cộng 8 điểm rèn luyện (hoạt động học thuật, nghiên cứu khoa học).\nHạn nộp sản phẩm: 23h59 ngày 22/12/2026."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} GIẢI CHẠY VIỆT DÃ SINH VIÊN HCMUS 2027.\nThời gian: 06h00 - 09h00, ngày 24/01/2027.\nĐịa điểm: Công viên Tao Đàn, Quận 1.\nVận động viên là sinh viên hoàn thành cự ly được cộng 5 điểm rèn luyện (hoạt động thể dục thể thao).\nĐăng ký trước 23h59 ngày 15/01/2027."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} ĐÊM NHẠC GIAO LƯU \"ÂM NHẠC VÀ TUỔI TRẺ\" CHÀO ĐÓN NĂM MỚI.\nThời gian: 19h00 - 21h30, ngày 28/12/2026.\nĐịa điểm: Sân Trường, Cơ sở Nguyễn Văn Cừ.\nSinh viên tham gia đầy đủ được cộng 3 điểm rèn luyện cho hoạt động văn hóa, văn nghệ.\nNhận vé tại văn phòng Đoàn Khoa trước ngày 26/12/2026."},
    # ---------------- Bổ sung: 2 mẫu/nhãn (tổng 36 mẫu) ----------------
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} THÔNG BÁO KHẢO SÁT Ý KIẾN SINH VIÊN VỀ CHẤT LƯỢNG CĂN TIN. Sinh viên đang ở ký túc xá vui lòng hoàn thành phiếu khảo sát trực tuyến trước 30/11/2026. Kết quả khảo sát dùng để cải thiện dịch vụ, không tổ chức hoạt động nào kèm theo."},
    {"label": "NOT_RELEVANT", "text":
     f"{DEMO} ƯU ĐÃI DÀNH RIÊNG CHO SINH VIÊN HCMUS KHI MUA LAPTOP GAMING. Nhà tài trợ XYZ ưu đãi giảm 20% cho sinh viên khi xuất trình thẻ sinh viên tại cửa hàng. Chương trình diễn ra từ 15/11 đến 15/12/2026, số lượng có hạn."},

    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} CHƯƠNG TRÌNH GIAO LƯU VỚI SINH VIÊN QUỐC TẾ SẼ TỔ CHỨC TRONG HỌC KỲ NÀY. Sinh viên quan tâm vui lòng theo dõi fanpage để biết lịch và địa điểm cụ thể. Nội dung sẽ được cập nhật sau khi Ban Tổ chức chốt kế hoạch."},
    {"label": "INSUFFICIENT_INFO", "text":
     f"{DEMO} BUỔI CHIA SẺ VỀ CHƯƠNG TRÌNH HỌC BỔNG TRAO ĐỔI CỦA TRƯỜNG. Thời gian: 18h00 - 20h00, ngày 09/12/2026. Địa điểm sẽ thông báo tới sinh viên đăng ký qua email. Sinh viên đăng ký để nhận thông tin chi tiết."},

    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} NGÀY HỘI XUÂN VIETNAMESE TET FESTIVAL 2027 - GIAN HÀNG TRUYỀN THỐNG.\nThời gian: 16h00 - 21h00, ngày 20/01/2027.\nĐịa điểm: Sân Trường, Cơ sở Nguyễn Văn Cừ.\nSinh viên tham quan gian hàng, tham gia trò chơi dân gian. Đăng ký làm tình nguyện viên trước 20h00 ngày 15/01/2027."},
    {"label": "EVENT_CANDIDATE", "text":
     f"{DEMO} TALKSHOW \"KỸ NĂNG PHỎNG VẤN VÀ CHUẨN BỊ CV\" CÙNG CỰU SINH VIÊN.\nThời gian: 14h00 - 16h30, ngày 15/12/2026.\nĐịa điểm: Phòng B.301, Cơ sở Nguyễn Văn Cừ.\nSinh viên quan tâm đăng ký trước 23h59 ngày 13/12/2026 qua form của Đoàn Khoa."},

    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} CUỘC THI VẬT LÝ TRỊ NHỚ \"MŨ LỆNH CHÂN LÝ\" MÙA 4.\nThời gian: 08h30 - 11h30, ngày 27/12/2026.\nĐịa điểm: Hội trường II, Cơ sở Linh Trung.\nThí sinh tham gia và hoàn thành các vòng thi được cộng 4 điểm rèn luyện (hoạt động học thuật).\nĐăng ký trước 23h59 ngày 24/12/2026."},
    {"label": "POTENTIAL_DRL", "text":
     f"{DEMO} LỄ TRI ÂN VÀ KHEN THƯỞNG SINH VIÊN CÓ THÀNH TÍCH XUẤT SẮC - ĐOÀN KHOA SINH HỌC.\nThời gian: 15h00 - 17h00, ngày 22/12/2026.\nĐịa điểm: Hội trường I, Cơ sở Nguyễn Văn Cừ.\nSinh viên thực hiện tốt phong trào thi đua năm học được cộng 3 điểm rèn luyện (hoạt động văn hóa gắn kết cộng đồng).\nTham dự và nhận giấy khen tại buổi lễ."},
]


# ---------------------------------------------------------------------------
# Hàm seed
# ---------------------------------------------------------------------------
def demo_sync_payload() -> dict:
    """Gói JSON mẫu chuẩn Schema 2 (dùng để test luồng đồng bộ, gắn nhãn [DEMO])."""
    from datetime import datetime
    progress = []
    criteria_map = {c["code"]: c for c in DEMO_CRITERIA}
    for row in DEMO_PROGRESS:
        crit = criteria_map[row["criterion_code"]]
        progress.append({
            "criterion_code": row["criterion_code"],
            "name": crit["name"],
            "current_score": row["current_score"],
            "max_score": crit["max_score"],
            "mandatory": crit["mandatory"],
        })
    return {
        "sync_source": config.SYNC_SOURCE_TAG,
        "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "is_demo": True,
        "demo_note": f"{DEMO} Gói dữ liệu mẫu phục vụ kiểm thử luồng tích hợp – không phải dữ liệu thật.",
        "student_profile": {
            "student_id": DEMO_STUDENT_ID,
            "full_name": f"{DEMO} Nguyễn Văn A",
            "semester": "HK1_2026_2027",
            "current_total_score": sum(r["current_score"] for r in DEMO_PROGRESS),
            "score_type": config.SCORE_TYPE_OFFICIAL,
            "has_detailed_criteria": True,
        },
        "drl_progress": progress,
        "timetable": [
            {**row, "source": "portal.ctdb.hcmus.edu.vn", "is_demo": True}
            for row in DEMO_SCHEDULE
        ],
    }


def seed_database(db_path=None, force: bool = False) -> dict:
    """Seed toàn bộ dữ liệu [DEMO] nếu DB đang trống (hoặc ``force=True``)."""
    database.init_db(db_path)
    stats = database.dashboard_stats(db_path)
    already = stats["n_posts"] > 0 or stats["n_criteria"] > 0
    if already and not force:
        return {"seeded": False, "reason": "Database đã có dữ liệu – bỏ qua seed."}

    if force:
        with database.transaction(db_path) as conn:
            for table in ("Activities", "SourcePosts", "StudentCriterionProgress",
                          "StudentSchedule", "StudentProfile", "DRLCriteria",
                          "AIAnalyses"):
                conn.execute(f"DELETE FROM {table}")

    # --- Tiêu chí ĐRL ---
    for crit in DEMO_CRITERIA:
        database.upsert_criterion({**crit, "is_demo": True}, db_path)

    # --- Nguồn OSA ---
    source_id = database.ensure_default_source(db_path)

    # --- Hồ sơ + tiến độ ---
    criteria_map = {c["code"]: c for c in DEMO_CRITERIA}
    progress_rows = [
        {
            "criterion_code": row["criterion_code"],
            "current_score": row["current_score"],
            "max_score": criteria_map[row["criterion_code"]]["max_score"],
            "status": "SYNCED",
        }
        for row in DEMO_PROGRESS
    ]
    total = sum(r["current_score"] for r in progress_rows)
    database.upsert_profile({
        "student_id": DEMO_STUDENT_ID,
        "full_name": f"{DEMO} Nguyễn Văn A",
        "faculty": "Khoa Công nghệ Thông tin",
        "semester": "HK1_2026_2027",
        "current_total_score": total,
        "score_type": config.SCORE_TYPE_OFFICIAL,
        "target_score": 90,
        "has_detailed_criteria": True,
    }, db_path)
    database.replace_criterion_progress(DEMO_STUDENT_ID, "HK1_2026_2027", progress_rows, db_path)

    # --- Thời khóa biểu ---
    database.replace_schedule(DEMO_STUDENT_ID, "HK1_2026_2027", DEMO_SCHEDULE,
                              synced_from=config.SYNC_SOURCE_TAG, is_demo=True, db_path=db_path)

    # --- Bài đăng + hoạt động ---
    catalog = [dict(c) for c in DEMO_CRITERIA]
    activity_ids: dict[str, int] = {}
    for post in DEMO_POSTS:
        report = nlp_engine.analyze_post(post["text"], url=config.OSA_FACEBOOK_URL, criteria_catalog=catalog)
        activity = report["activity"]
        flags = report["missing_flags"]
        post_id = database.insert_source_post(
            source_id=source_id,
            raw_text=post["text"],
            url=config.OSA_FACEBOOK_URL,
            fetch_method=post["fetch_method"],
            external_post_id=f"demo-{post['key']}",
            relevance_label=report["relevance_label"],
            rejection_reason=report["extraction_meta"].get("rejection_reason"),
            is_demo=True,
            db_path=db_path,
        )
        state = DEMO_POST_STATE.get(post["key"], {})
        is_verified = bool(state.get("verified"))
        label = config.LABEL_VERIFIED if is_verified else report["relevance_label"]
        status = config.VERIFY_ADMIN_APPROVED if is_verified else report["drl_assessment"]["status"]
        explanation = report["drl_assessment"]["reason"]
        if is_verified:
            explanation = f"{explanation}\n\n{state.get('verified_note', '')}"
        act_id = database.insert_activity({
            "source_post_id": post_id,
            "parent_activity_id": None,
            "title": activity["title"],
            "description": post["text"][:1200],
            "organizer": activity["organizer"],
            "location": activity["location"],
            "campus": activity["campus"],
            "start_time": activity["start_time"],
            "end_time": activity["end_time"],
            "registration_deadline": activity["registration_deadline"],
            "expected_score": activity["expected_score"],
            "criterion_code": activity["criterion_code"],
            "relevance_label": label,
            "verification_status": status,
            "is_missing_time": int(flags["is_missing_time"]),
            "is_missing_location": int(flags["is_missing_location"]),
            "is_missing_content": int(flags["is_missing_content"]),
            "is_missing_score": int(flags["is_missing_score"]),
            "ai_explanation": explanation,
            "ai_source": "LOCAL_NLP (Regex/Heuristic) – DEMO SEED",
            "is_demo": True,
        }, db_path)
        activity_ids[post["key"]] = act_id

    # --- Nối bài "nhắc hạn" vào sự kiện gốc (parent_activity_id) ---
    for key, state in DEMO_POST_STATE.items():
        parent_key = state.get("link_parent")
        if parent_key and parent_key in activity_ids and key in activity_ids:
            database.link_parent_activity(activity_ids[key], activity_ids[parent_key], db_path)

    database.log_action("SEED_DEMO_DATA", {
        "posts": len(DEMO_POSTS),
        "criteria": len(DEMO_CRITERIA),
        "schedule": len(DEMO_SCHEDULE),
        "student_id": DEMO_STUDENT_ID,
        "note": f"{DEMO} Dữ liệu khởi tạo tự động",
    }, db_path)
    return {"seeded": True, "posts": len(DEMO_POSTS), "criteria": len(DEMO_CRITERIA)}


def export_benchmark_csv(path: Optional[str] = None) -> "object":
    """Xuất tập Benchmark ra CSV để nhóm nộp kèm báo cáo."""
    import csv
    from pathlib import Path

    out = Path(path) if path else config.DATA_DIR / "ml_benchmark_dataset.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["sample_id", "label", "text"])
        writer.writeheader()
        for idx, row in enumerate(BENCHMARK_DATASET, start=1):
            writer.writerow({"sample_id": f"BENCH-{idx:03d}", "label": row["label"], "text": row["text"]})
    return out


if __name__ == "__main__":  # pragma: no cover
    print(seed_database())
    print("Xuất benchmark:", export_benchmark_csv())
