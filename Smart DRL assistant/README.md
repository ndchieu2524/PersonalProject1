# 🎓 Smart DRL Assistant – HCMUS (MVP v1.0)

Hệ thống hỗ trợ sinh viên **Trường Đại học Khoa học Tự nhiên – ĐHQG TP.HCM** đồng bộ
Thời khóa biểu + Điểm rèn luyện (ĐRL), phân tích bài đăng hoạt động từ fanpage **OSA HCMUS**,
và tối ưu **lộ trình tham gia** bằng đồ thị NetworkX sao cho không trùng lịch học.

> ⚠️ **Toàn bộ dữ liệu khởi tạo sẵn đều gắn nhãn `[DEMO]`.** Điểm ĐRL trên hệ thống chỉ mang
> tính tham khảo & hỗ trợ ra quyết định; điểm chính thức do Phòng Công tác Sinh viên – HCMUS
> quyết định theo quy chế hiện hành trên `hcmus.drl.vn`.

---

## 1. Cài đặt & chạy trong 3 bước

```bash
# Bước 1 – Cài thư viện (bắt buộc theo đề bài + 3 gói tuỳ chọn cho module AI)
pip install streamlit pandas networkx scikit-learn matplotlib google-generativeai
# (tuỳ chọn) dùng OpenAI:  pip install openai
# (tuỳ chọn) đọc file Excel ở Tab 2:  pip install openpyxl

# Bước 2 – Chạy ứng dụng (đứng tại thư mục gốc của project)
streamlit run app.py

# Bước 3 – Mở http://localhost:8501
#   Lần chạy đầu tiên hệ thống tự tạo smart_drl_mvp.db và seed toàn bộ dữ liệu [DEMO].
```

Chạy kiểm thử tự động (31 test):

```bash
pip install pytest
pytest tests/ -q          # 33 test Python: NLP, Schema, SQLite, NetworkX, ML, hồi quy dữ liệu thật
```

Kiểm thử **extension** trên đúng bảng CTĐB thật (cần Node.js ≥ 18):

```bash
cd devtests
npm install
npm test                  # 22 kiểm chứng: tách 7 buổi học + phòng, MSSV, học kỳ, gói JSON Schema 2
```

`devtests/` **không** cần cho việc cài extension — chỉ dùng khi bạn muốn kiểm chứng lại bộ đọc DOM.

---

## 0. Bạn đang chạy đúng bản chưa? (kiểm tra 10 giây)

Bản mới nhất phải có **7 tab**, trong đó có **🌐 Thu thập TỰ ĐỘNG**.
Nếu thanh tab chỉ có 6 tab → bạn đang chạy **thư mục giải nén cũ**.

```bash
python check_version.py
```

Kết quả mong đợi: `✅ ĐÂY LÀ BẢN MỚI – có 7 tab`.

**Cách sửa khi bị nhầm bản:**

1. **Tắt hẳn** cửa sổ cmd đang chạy app (đóng cửa sổ, không chỉ bấm Ctrl+C).
2. Giải nén `smart_drl_assistant.zip` vào thư mục **MỚI** (ví dụ `D:\smart_drl_v2`).
3. Vào thư mục mới, chạy `run.bat`. Cửa sổ cmd sẽ in:
   `Phien ban 2.0.0-CRAWLER` và `[OK] Da tim thay bo thu thap tu dong`.
4. Mở `http://localhost:8501` — sidebar hiện **Phiên bản 2.0.0-CRAWLER** và mục
   **🔎 Đang chạy từ thư mục nào?** để bạn đối chiếu đường dẫn.

> App **tự thu thập dữ liệu thật ngay lần đầu mở** (nếu kho chưa có hoạt động thật),
> nên bạn không cần bấm gì cũng thấy dữ liệu thật ở Tab 🗂️ Kho hoạt động.

---

## 1b. Thu thập TỰ ĐỘNG từ cổng công khai HCMUS (Tab 2)

Tab **🌐 Thu thập TỰ ĐỘNG** tự đi lấy hoạt động/sự kiện/workshop — **không cần dán link,
không cần đăng nhập, không cần extension**. Chỉ bấm **🚀 Bắt đầu thu thập**.

### Bốn nguồn thật đang dùng

| Nguồn | Cách đọc | Dữ liệu có sẵn |
|---|---|---|
| **Phòng Công tác Sinh viên**<br>`ctsv.hcmus.edu.vn` | API JSON công khai `/api/news` (457 bài, phân trang) | Tiêu đề, nội dung đầy đủ, ngày đăng, chuyên mục, tác giả |
| **Lịch sự kiện Trường**<br>`hcmus.edu.vn/events` | The Events Calendar REST API (55 sự kiện) | **Có sẵn start/end + địa điểm + đơn vị tổ chức** |
| **Tin tức/Thông báo Trường**<br>`hcmus.edu.vn` | WordPress REST API `/wp-json/wp/v2/posts` | Tiêu đề, nội dung HTML, ngày đăng |
| **Khoa CNTT**<br>`fit.hcmus.edu.vn/tin-tuc/c/thong-bao-chung` | Phân tích HTML danh sách | Tiêu đề, mô tả, ngày đăng, link bài |

### Quy trình

1. Tab 2 → chọn nguồn → đặt **Số trang** (1 trang ≈ 50 bài) → **🚀 Bắt đầu thu thập**.
2. Hệ thống gọi API, lọc bỏ tin hành chính (học phí, bảo hiểm y tế, lịch thi, tin đã diễn ra…),
   hiển thị bảng xem trước kèm cột **Mời tham gia** = ✅ cho bài có lời mời đăng ký.
3. Bấm **💾 Lưu tất cả vào SQLite** → mỗi bài chạy qua pipeline NLP để bóc tách
   thời gian / địa điểm / đơn vị / điểm ĐRL rồi ghi vào `Activities`.

### Trung thực về Facebook

`facebook.com` trả về **trang đăng nhập** cho mọi request không kèm cookie, nên **không thể**
thu thập tự động bài fanpage. Tab 2 có nút **🔍 Kiểm tra khả năng đọc Facebook (thử thật)** để
bạn tự thấy bằng chứng (URL cuối cùng sẽ là `facebook.com/login`). Cách hợp lệ:
dùng **Chrome Extension** (đọc DOM khi chính bạn đang đăng nhập) hoặc dán nội dung vào Tab 3.

### ✅ Cổng chặn: ĐỦ THÔNG TIN mới được vào kho

Mặc định hệ thống **chỉ lưu hoạt động có đủ 4 thông tin bắt buộc**:

| Trường | Ví dụ |
|---|---|
| Tiêu đề | Đăng ký tham dự Hội thảo: Xây dựng CV nổi bật… |
| **Ngày diễn ra** | `2026-11-18 14:00` |
| **Địa điểm** | `Phòng I.23 cơ sở Nguyễn Văn Cừ` |
| **Đơn vị tổ chức** | `Khoa Công nghệ Thông tin – HCMUS` |

Ngoài ra hệ thống **bóc thêm** (nếu bài có ghi):
**thời lượng** (`14g00 - 16g00` → 120 phút), **diễn giả / báo cáo viên**, **hạn đăng ký**.

Mục thiếu bất kỳ trường nào **bị chặn**, hiện trong bảng "⛔ N mục bị chặn vì THIẾU
thông tin" kèm lý do và link gốc — bạn tự mở xem nếu muốn nhập tay.

Tab 🗂️ Kho hoạt động có mục **"🔍 Câu gốc dùng để bóc ngày"**: mỗi ngày đều truy vết
được về đúng câu trong bài đăng, không có chuyện đoán.

#### Vì sao phải tách "hạn nộp" khỏi "ngày diễn ra"

Trong văn bản CTSV, **phần lớn ngày là hạn chót** (nộp hồ sơ, đóng phí, khiếu nại).
Bóc bừa mọi ngày sẽ khiến kho lưu một workshop với ngày hết hạn đăng ký thay vì ngày
diễn ra — sinh viên tưởng đã hết hạn và bỏ lỡ buổi thật. Hệ thống nhận diện nhãn
(`Thời gian:`, `Địa điểm:`, `Báo cáo viên:`) và các cụm hạn chót
(`đến hết ngày`, `hạn cuối`, `chậm nhất`, `tính tích luỹ`…) để phân biệt.

### ⏳ Chỉ lấy hoạt động CHƯA DIỄN RA

Mặc định hệ thống **bỏ mọi sự kiện đã kết thúc**. Có 3 lớp lọc:

1. **Ở nguồn** — với nguồn sự kiện có sẵn `start/end`, so sánh **ngày kết thúc** với hôm nay
   (hội nghị 09–16/11 vẫn được giữ nếu hôm nay là 14/11).
2. **Sau khi phân tích NLP** — bài tin tức không có ngày cấu trúc sẽ được bóc ngày từ văn bản
   rồi lọc lại; bài ghi *"đã diễn ra"*, *"recap"*, *"danh sách tham dự"* bị loại từ đầu.
3. **Trong Tab 🗂️ Kho hoạt động** — mục **"⏳ Ẩn hoạt động đã diễn ra"** bật mặc định;
   Tab 🌐 Thu thập có nút **🧽 Xoá hoạt động thật đã kết thúc** để dọn kho cũ.

Mục **không ghi ngày ở đâu cả** vẫn được giữ (không đủ căn cứ kết luận đã xong) — bạn tự kiểm tra.

> **Lưu ý thực tế:** trang Lịch sự kiện của trường hiện **không có sự kiện nào sắp tới**
> (mới nhất là 09–12/11/2026 đã qua), nên nguồn này chỉ còn 1 mục. Đó là dữ liệu thật,
> không phải lỗi — khi trường đăng sự kiện mới, lần thu thập sau sẽ tự bắt được.

### Chất lượng bóc tách trên dữ liệu thật (đo ngày 14/11/2026)

Chạy 3 trang/nguồn → **129 hoạt động thật** (Chưa tính 11 mục [DEMO]):

| Trường | Tỷ lệ có dữ liệu |
|---|---|
| Thời gian (ngày + giờ) | **107/129 (83%)** |
| Địa điểm | **66/129 (51%)** |
| Đơn vị tổ chức | **129/129 (100%)** |

Phần thiếu là do bài gốc **thật sự không ghi** (ví dụ tin tuyển sinh, thông báo chung),
không phải hệ thống bỏ sót. Hệ thống **không suy đoán** ngày/giờ/phòng còn thiếu —
thà để trống còn hơn điền sai.

### Ghi chú kỹ thuật

* Chỉ đọc trang **công khai**; không đăng nhập, không vượt CAPTCHA, không gửi dữ liệu ra ngoài.
* Nghỉ 0,35 giây giữa các request để không làm nặng server trường.
* Theo yêu cầu hiện tại: **cho phép trùng lặp** — mỗi lượt thu thập ghi thêm bản ghi mới.
  Khi cần, dùng nút **🧹 Gộp hoạt động trùng lặp** ở cuối Tab 2 (giữ 1 bản/nhóm và
  bổ sung các trường còn trống từ bản khác).
* Dữ liệu tự thu thập có `is_demo = 0`, tách biệt hoàn toàn với dữ liệu mẫu `[DEMO]`.
* **Định dạng tiếng Việt được hỗ trợ:** `13g30`, `08h30`, `8 giờ 30`, `08:30`; ngày `dd/mm/yyyy`.
  Giờ hành chính (*"Giờ làm việc: 8:00 – 11:30"*) được nhận diện và **bỏ qua** vì không phải
  giờ diễn ra hoạt động.

## 2. Cài Chrome Extension (Manifest V3)

1. Mở `chrome://extensions` → bật **Developer mode**.
2. Bấm **Load unpacked** → chọn thư mục `chrome_plugin/`.
3. Tự đăng nhập cổng `portal.ctdb.hcmus.edu.vn` → mở **Đăng ký học phần → Kết quả ĐKHP**
   (bảng *"CÁC MÔN ĐÃ ĐĂNG KÝ"*) → bấm biểu tượng extension → **🔄 Quét trang**.
   Extension đọc đúng các ô `Lịch LT / Lịch TH` dạng `T3 07:30-11:10` + dòng phòng `(E402)`
   bên dưới, tách **mỗi buổi học thành một dòng** (môn có 2 buổi → 2 dòng), và tự điền **MSSV**
   + **học kỳ** (`HK1_2026_2027`) đọc từ trang.
4. Tự đăng nhập `hcmus.drl.vn` → mở trang **Điểm rèn luyện** → **🔄 Quét trang**.
5. Bấm **⬇️ Xuất hcmus_sync.json** → Web App → **Tab 1** → tải file lên.

> **Về cột “Cơ sở”:** bảng CTĐB của trường **không** ghi cơ sở học (chỉ có mã phòng).
> Vì vậy popup có ô **Cơ sở mặc định** — bạn tự chọn *Nguyễn Văn Cừ* / *Linh Trung* / *Trực tuyến*.
> Nếu để trống, app sẽ **không tự bịa** cơ sở mà coi là chưa xác định.
>
> **Quét 2 trang theo thứ tự bất kỳ:** mỗi lần quét chỉ điền phần dữ liệu của trang đó.
> Gói chỉ có thời khóa biểu (chưa quét DRL) **không ghi đè** điểm rèn luyện đã đồng bộ trước đó —
> app giữ nguyên và hiện cảnh báo màu vàng.

Nếu HTML cổng trường thay đổi hoặc cần kiểm thử offline: bấm
**🧪 Tạo gói JSON Mẫu Chuẩn HCMUS (Demo Sync)** — gói sinh ra hợp lệ và gắn nhãn `[DEMO]`.

**Cam kết bảo mật:** extension chỉ đọc DOM khi bạn đã tự đăng nhập; **không** đọc/lưu mật khẩu,
cookie hay token; **không** vượt CAPTCHA; **không** gửi dữ liệu ra bất kỳ server nào.

---

## 3. Cấu trúc project

```
smart_drl_assistant/
├── app.py                      # Cửa vào Streamlit – 6 tab
├── drl/
│   ├── config.py               # Hằng số, nhãn nghiệp vụ, thông điệp cảnh báo
│   ├── database.py             # SQLite: schema 8 bảng + helper truy vấn
│   ├── seed_data.py            # Dữ liệu [DEMO] + 36 mẫu Benchmark
│   ├── nlp_engine.py           # Bóc tách Regex/Heuristic + phân loại 2 bước (offline)
│   ├── ai_engine.py            # Gemini / OpenAI Structured JSON + fallback nội bộ
│   ├── ml_benchmark.py         # Baseline Keyword vs TF-IDF + LogisticRegression
│   ├── pathway.py              # NetworkX DAG + QHĐ tôn trọng trần điểm tiêu chí
│   ├── ui_common.py            # CSS, badge, bảng Pandas tô màu, đồng bộ Schema 2
│   ├── ui_sidebar.py           # Cấu hình AI + cam kết bảo mật
│   ├── ui_tab1_dashboard.py    # Tab 1 – Dashboard & Đồng bộ Plugin
│   ├── ui_tab2_ingest.py       # Tab 2 – Thu thập & bóc tách OSA (4 phương thức)
│   ├── ui_tab3_explorer.py     # Tab 3 – Kho hoạt động & cảnh báo dữ liệu khuyết
│   ├── ui_tab4_pathway.py      # Tab 4 – Lộ trình tối ưu & kiểm tra trùng lịch
│   ├── ui_tab5_criteria.py     # Tab 5 – Quản lý quy chế ĐRL
│   └── ui_tab6_ml.py           # Tab 6 – Thực nghiệm & đánh giá mô hình ML
├── chrome_plugin/
│   ├── manifest.json           # Manifest V3
│   ├── content.js              # Trích xuất DOM 2 cổng (bảng tiêu đề / lưới thứ / thẻ môn)
│   ├── popup.html / popup.css / popup.js
│   └── icons/                  # 16 / 48 / 128 px
├── data/
│   ├── smart_drl_mvp.db        # SQLite tự sinh
│   └── ml_benchmark_dataset.csv# Xuất từ Tab 6
├── tests/test_core.py          # 31 test (pytest)
└── docs/HUONG_DAN_SU_DUNG.md   # Hướng dẫn sử dụng + kịch bản demo
```

---

## 4. Kiến trúc 2 phân hệ

```
┌──────────────────────────── Trình duyệt (đã đăng nhập) ───────────────────────────┐
│  portal.ctdb.hcmus.edu.vn          hcmus.drl.vn                                    │
│         │  content.js đọc DOM              │  content.js đọc DOM                  │
│         └────────────┬─────────────────────┘                                       │
│                 popup.js  ──►  hcmus_sync.json  (Schema 2, có [DEMO] fallback)      │
└───────────────────────────────────┬────────────────────────────────────────────────┘
                                    │  JSON / clipboard / file
┌───────────────────────────────────▼────────────────────────────────────────────────┐
│  WEB APP (Streamlit)                                                               │
│  SQLite smart_drl_mvp.db  ←  Pandas  ←  NLP Regex/Heuristic  ←(tuỳ chọn) Gemini/OpenAI │
│                                   │                                                │
│                     NetworkX DAG + QHĐ trần điểm  ──►  Lộ trình + Route Explanation │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Quy tắc nghiệp vụ đã cài đặt (đối chiếu đề bài)

| Yêu cầu | Nơi cài đặt |
|---|---|
| Phân loại **2 bước** + 4 nhóm thông tin | `nlp_engine.classify_two_step`, `_compute_missing_flags` |
| Tự động bật cờ `is_missing_*` & tô đỏ trên bảng Pandas | `nlp_engine`, `ui_common.style_activity_table` |
| **Không tự bịa điểm**: không có câu nêu điểm → `expected_score = None`, nhãn `EVENT_CANDIDATE` / `INSUFFICIENT_INFO` | `nlp_engine.extract_score` |
| Chỉ nhập tổng điểm → banner cảnh báo, **không chia đều** tiêu chí | `config.WARNING_TOTAL_SCORE_ONLY`, Tab 1 |
| 3 loại điểm trên Dashboard (Hiện tại / Verified / Potential) + Mục tiêu | `ui_tab1_dashboard._metric_row` |
| `POTENTIAL_DRL` **không** cộng vào điểm chính thức | `pathway.compute_optimal_pathway` (tách `verified_gain` / `potential_gain`) |
| AI **không được** tự nâng `VERIFIED_DRL` | `ai_engine.sanitize_ai_report` + test `test_ai_cannot_self_verify` |
| Gợi ý `parent_activity_id` cho bài nhắc hạn / đổi lịch / kết quả | `nlp_engine.suggest_parent_activity`, Tab 3 |
| Chấp nhận **dữ liệu trùng lặp** ở MVP, chỉ lưu `content_hash` | `database.insert_source_post` + test `test_content_hash_present_and_duplicates_allowed` |
| NetworkX: lọc trùng lịch → DAG → đường đi tối ưu → giải thích | `pathway.py` (3 bước + `explain_route_*`) |
| Di chuyển NVC ↔ Linh Trung = 45 phút | `config.TRAVEL_MATRIX` |
| Trần `max_score` từng tiêu chí được tôn trọng | `pathway.dynamic_programming_path` |
| Benchmark ML: Baseline vs TF-IDF + LR, đủ Accuracy/P/R/F1 + Confusion Matrix | `ml_benchmark.py`, Tab 6 |
| 8 bảng SQLite đúng tên cột | `database.SCHEMA_SQL` |
| Schema 1 (AI Analyzer) & Schema 2 (Extension Sync) | `nlp_engine.analyze_post`, `ui_common.apply_sync_payload` |
| 4 phương thức nạp bài đăng OSA (URL, CSV/Excel, ảnh poster, bộ DEMO) | Tab 2 |
| Fallback DEMO trên extension | nút **Tạo gói JSON Mẫu Chuẩn HCMUS** |

### Thang nhãn & xử lý

| Nhãn | Tính vào điểm | Vào lộ trình |
|---|---|---|
| `NOT_RELEVANT` | Không | Không (tab riêng để Admin rà soát) |
| `INSUFFICIENT_INFO` | Không | Không (cảnh báo đỏ, chờ bổ sung) |
| `EVENT_CANDIDATE` | Không | Không (hiển thị "Chưa rõ quyền lợi ĐRL") |
| `POTENTIAL_DRL` | Chỉ cột **Dự kiến** | Có, gắn nhãn "tiềm năng" |
| `VERIFIED_DRL` | Cột **Đã xác minh** | Có, ưu tiên |

---

## 5b. Xử lý sự cố khi quét cổng trường

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Bấm **Quét trang** mà popup báo *0 buổi học* | Extension cũ còn nạp trong Chrome (Load unpacked giữ bản trước) | Vào `chrome://extensions` → bấm **🔄 (Reload)** trên thẻ extension → tải lại trang portal → quét lại |
| Báo *"Trang không thuộc 2 cổng hỗ trợ"* | Đang mở tab khác | Mở đúng tab `portal.ctdb.hcmus.edu.vn` hoặc `hcmus.drl.vn` rồi mới bấm quét |
| Đọc được môn nhưng **phòng trống** | Ô lịch chỉ có `T2 07:30-11:10` (trường chưa xếp phòng) | Bình thường — bảng thật có buổi không ghi phòng (VD môn *Thực tập 1*). App hiển thị `—` |
| Cột **Cơ sở** trống | Bảng CTĐB không có cột cơ sở | Chọn **Cơ sở mặc định** trong popup trước khi xuất gói |
| Portal đổi giao diện, không đọc được gì | Cấu trúc HTML mới | Dùng nút **🧪 Tạo gói JSON Mẫu Chuẩn HCMUS (Demo Sync)** để chạy tiếp luồng tích hợp |

## 6. Module AI (tuỳ chọn, luôn có fallback)

Sidebar → chọn **Gemini** hoặc **OpenAI**, nhập API Key (chỉ lưu trong phiên, không ghi DB,
không ghi log) → bấm **Kiểm tra kết nối**.

- Nếu chưa có key / mạng lỗi / JSON hỏng → tự động dùng **NLP nội bộ (Regex/Heuristic)**.
- Mọi kết quả AI đều qua `sanitize_ai_report`: hạ `VERIFIED_DRL` tự phong, loại mã tiêu chí
  không tồn tại, tính lại cờ `is_missing_*` trên dữ liệu cuối.
- OCR poster dùng **Gemini Vision**; khi chưa có key, giao diện nói rõ là chưa OCR và hướng
  dẫn dán văn bản — **không giả vờ** đã trích xuất.

---

## 7. Báo cáo thực nghiệm (Tab 6)

Tập Benchmark: **36 mẫu** `[DEMO]` (9 mẫu/nhãn), chia stratified 70/30,
`random_state = 42`, kèm Stratified 3-Fold CV.

| Mô hình | Accuracy | Precision (macro) | Recall (macro) | F1 (macro) |
|---|---|---|---|---|
| Baseline – đếm từ khoá | ~0.45 | ~0.48 | ~0.46 | ~0.40 |
| TF-IDF (word+char) + đặc trưng cấu trúc + LogisticRegression | ~1.00 | ~1.00 | ~1.00 | ~1.00 |

Kết quả thực tế hiển thị động trên Tab 6 (số có thể thay đổi khi đổi `random_state`/tỉ lệ test).

**Giới hạn cần nêu khi báo cáo (đã ghi trong app):**
- 36 mẫu là ít; dữ liệu `[DEMO]` do nhóm biên soạn nên có thiên lệch văn phong.
- Bộ heuristic được phát triển cùng tập dữ liệu này → con số "luật" mang tính luật đã tinh chỉnh.
- Khi có dữ liệu OSA thật: thay `BENCHMARK_DATASET` trong `drl/seed_data.py`, pipeline đánh giá
  và biểu đồ tự chạy lại; nên gán nhãn độc lập 2 người + đo Cohen's Kappa.

---

## 8. Điểm cần lưu ý khi đưa vào sử dụng thật

1. **Quy chế ĐRL trong DB là khung [DEMO]** – phải đối chiếu `hcmus.drl.vn` và cập nhật ở Tab 5.
2. **Cấu trúc HTML của 2 cổng trường có thể thay đổi** – content.js đã xử lý 3 kiểu bảng
   (có tiêu đề cột, lưới thứ, thẻ môn) và có fallback DEMO, nhưng nên kiểm tra lại mỗi học kỳ.
3. **Facebook Graph API** không được dùng (giới hạn quyền fanpage) — 4 phương thức nạp thủ công
   là hợp lệ và đúng chủ trương.
4. **Không thu thập dữ liệu cá nhân ngoài phạm vi cần thiết**; `AuditLogs` lưu vết thao tác Admin.
5. Giờ kết thúc của bài đăng không ghi rõ được **giả định +2 giờ** và hiển thị minh bạch trong
   `assumptions` – cần xác minh trước khi dùng thật.

---

## 9. Lệnh pip đầy đủ (theo đề bài)

```bash
pip install streamlit pandas networkx scikit-learn matplotlib google-generativeai
```

Tuỳ chọn thêm: `pip install openai openpyxl pytest`
