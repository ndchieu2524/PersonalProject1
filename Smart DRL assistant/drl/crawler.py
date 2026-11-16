"""Thu thập TỰ ĐỘNG hoạt động/sự kiện từ các cổng công khai của HCMUS.

Triết lý thiết kế
-----------------
* Chỉ đọc **trang công khai** – không đăng nhập, không vượt CAPTCHA, không giả mạo
  phiên người dùng. Mỗi nguồn đều ghi rõ URL gốc để người dùng kiểm chứng.
* Không bịa: trường nào trang nguồn không có thì để trống + bật cờ `is_missing_*`.
  Tuyệt đối không suy đoán điểm ĐRL, không tự thêm địa điểm, không tự đặt ngày.
* Năm adapter, chạy độc lập, một nguồn lỗi không làm hỏng cả lượt thu thập:

  1. ``ctsv_api``        – JSON API công khai của Phòng Công tác Sinh viên
                           ``https://ctsv.hcmus.edu.vn/api/news`` (có phân trang)
  2. ``hcmus_events``    – The Events Calendar REST API của Trường
                           ``https://hcmus.edu.vn/wp-json/tribe/events/v1/events``
  3. ``hcmus_posts``     – WordPress REST API bài viết thông báo của Trường
                           ``https://hcmus.edu.vn/wp-json/wp/v2/posts``
  4. ``fit_news``        – HTML danh sách thông báo Khoa CNTT
                           ``https://fit.hcmus.edu.vn/tin-tuc/c/thong-bao-chung``
  5. ``fb_rss``          – RSS Feed Fanpage Facebook trung gian
"""
from __future__ import annotations

import html as html_lib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Iterable, Optional
from urllib.parse import urljoin

import feedparser
import requests

from . import config, event_details

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 25
DEFAULT_DELAY = 0.35          # giây giữa các request – lịch sự với server trường
MAX_PAGES_HARD_LIMIT = 30     # chặn vòng lặp vô hạn

# Nhãn nguồn hiển thị trong UI
SOURCE_TYPE_LABELS = {
    "ctsv_api": "Phòng Công tác Sinh viên (API JSON)",
    "hcmus_events": "Trường HCMUS – Lịch sự kiện (API)",
    "hcmus_posts": "Trường HCMUS – Tin tức/Thông báo (API)",
    "fit_news": "Khoa CNTT – Thông báo (HTML)",
    "fb_rss": "Fanpage Facebook (qua RSS)",
}

# Từ khoá nhận diện nội dung là HOẠT ĐỘNG (không phải tin học vụ thuần tuý)
ACTIVITY_KEYWORDS = [
    "hội thảo", "hội nghị", "seminar", "workshop", "tập huấn", "khóa tập huấn",
    "cuộc thi", "hội thi", "olympic", "ngày hội", "giao lưu", "talkshow", "talk show",
    "tọa đàm", "toạ đàm", "chương trình", "chiến dịch", "tình nguyện", "hiến máu",
    "câu lạc bộ", "clb", "sự kiện", "event", "cuộc đua", "giải chạy", "liên hoan",
    "biểu diễn", "triển lãm", "tuyển thành viên", "tuyển cộng tác viên", "bootcamp",
    "hackathon", "job fair", "ngày hội việc làm", "định hướng nghề nghiệp",
    "pháp luật với sinh viên", "phiên tòa giả định", "tuyên truyền pháp luật",
    "tuần sinh hoạt công dân", "sinh hoạt chính trị", "giáo dục quốc phòng",
    "hiến máu", "hiến tạng", "chạy bộ", "giải chạy", "thể thao", "hội thao",
    "văn nghệ", "cuộc thi học thuật", "kỳ thi olympic", "mentor", "mentoring",
]

# Từ khoá loại trừ: tin học vụ/hành chính không phải hoạt động rèn luyện
EXCLUDE_KEYWORDS = [
    "học bổng", "miễn giảm học phí", "đóng học phí", "học phí", "bảo hiểm y tế",
    "khám sức khỏe", "tạm hoãn nghĩa vụ", "nghĩa vụ quân sự", "tốt nghiệp",
    "bằng tốt nghiệp", "chương trình đào tạo", "tuyển sinh", "đăng ký môn học",
    "lịch thi", "điểm thi", "phúc khảo", "xin xác nhận", "cấp giấy", "biểu mẫu",
    "báo giá", "mua sắm", "đấu thầu", "tuyển dụng giảng viên", "kết quả xét",
    "danh sách sinh viên", "lệ phí", "nghỉ lễ", "nghỉ tết", "nghỉ học",
    "chính sách tín dụng", "chính sách", "kết quả chính thức", "điểm rèn luyện sinh viên",
    "kết quả điểm rèn luyện", "thông báo kết quả", "công bố kết quả", "xét học bổng",
    "thu phí", "nộp hồ sơ", "gia hạn", "chuyển ngành", "chuyển trường",
    "bảo lưu", "thôi học", "cảnh báo học vụ", "thi lại", "học lại", "học cải thiện",
    "cấp bảng điểm", "xác nhận sinh viên", "thẻ sinh viên", "ký túc xá",
    "lịch sử dụng phòng", "lịch sử dụng", "lịch công tác", "lịch làm việc",
    "thông báo lịch", "phân công", "quy định mới", "quy chế", "quy định về",
    "bảo vệ thành công", "bảo vệ luận án", "luận án tiến sĩ", "luận văn",
    "kết luận của", "hội nghị tổng kết", "tổng kết năm", "sơ kết",
    "làm việc với", "tiếp đón đoàn", "đón tiếp đoàn", "thăm và làm việc",
    "ký kết", "biên bản ghi nhớ", "thỏa ước hợp tác", "hợp tác quốc tế",
    "chúc mừng", "vinh danh", "tôn vinh", "tri ân thầy cô",
    "bổ nhiệm", "miễn nhiệm", "quyết định bổ nhiệm",
    "đạt giải", "giành giải", "đoạt giải", "giải thưởng sinh viên",
    "newsletter", "bản tin", "kế hoạch giảng dạy", "kế hoạch học tập",
    "thời khóa biểu chính thức", "thông tin kế hoạch", "kế hoạch năm học",
    "sau đại học", "thạc sĩ", "tiến sĩ", "nghiên cứu sinh",
    "huy chương", "học sinh giỏi quốc gia", "thông tư", "nghị định",
    "quyền tự chủ", "giải trình", "chương trình ưu đãi", "triển khai chương trình phát triển",
    "recap", "tường thuật", "nhìn lại", "đã diễn ra", "kết thúc thành công",
    "tổng kết", "bế mạc", "trao giải", "danh sách tham dự", "danh sách trúng tuyển",
    "kết quả lựa chọn", "đã chọn được", "được chọn",
]


# ---------------------------------------------------------------------------
# Kiểu dữ liệu
# ---------------------------------------------------------------------------
@dataclass
class CrawledPost:
    """Một bài/sự kiện thô thu được từ nguồn công khai (CHƯA phân loại)."""

    source_key: str
    source_name: str
    source_url: str
    external_id: str
    title: str
    content: str
    url: str
    published_at: str = ""
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    organizer: str = ""
    image_url: str = ""
    category: str = ""
    raw_extra: dict = field(default_factory=dict)

    @property
    def is_invitation(self) -> bool:
        """Bài có lời mời đăng ký/tham dự (ưu tiên hiển thị)."""
        return looks_like_invitation(self.title, self.content)

    def to_record(self) -> dict:
        """Chuyển thành dict để lưu/CSV."""
        return {
            "source_key": self.source_key,
            "source_name": self.source_name,
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "location": self.location,
            "organizer": self.organizer,
            "category": self.category,
            "content_len": len(self.content),
            "is_invitation": self.is_invitation,
            "content": self.content,
        }


@dataclass
class CrawlResult:
    """Kết quả một lượt thu thập."""

    source_key: str
    source_name: str
    ok: bool
    posts: list[CrawledPost] = field(default_factory=list)
    message: str = ""
    http_calls: int = 0
    elapsed_s: float = 0.0
    skipped_reason: str = ""

    @property
    def n(self) -> int:
        return len(self.posts)


# ---------------------------------------------------------------------------
# Tiện ích HTTP / văn bản
# ---------------------------------------------------------------------------
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    })
    return s


def html_to_text(raw_html: str) -> str:
    """Bóc HTML thô → văn bản thuần (giữ xuống dòng giữa các block)."""
    if not raw_html:
        return ""
    s = str(raw_html)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|section)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    s = s.replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def _clean(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(s or ""))).strip()


def is_upcoming(record: dict, now: Optional[datetime] = None, max_post_age_days: int = 14) -> Optional[bool]:
    """Mục này còn diễn ra / chưa diễn ra không?"""
    now = now or datetime.now()
    end_raw = str(record.get("end_time") or "").strip()
    start_raw = str(record.get("start_time") or "").strip()

    def parse(value: str) -> Optional[datetime]:
        if len(value) < 10:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value[:16] if ":" in value else value[:10], fmt)
            except ValueError:
                continue
        return None

    end_dt = parse(end_raw) or parse(start_raw)
    if end_dt is not None:
        return end_dt.date() >= now.date()

    # Nếu không có ngày diễn ra sự kiện, kiểm tra ngày đăng bài (published_at)
    pub_raw = str(record.get("published_at") or "").strip()
    if pub_raw:
        pub_dt = parse(pub_raw)
        if pub_dt is None:
            try:
                pub_dt = parsedate_to_datetime(pub_raw).replace(tzinfo=None)
            except Exception:
                pub_dt = None
        if pub_dt is not None and (now.date() - pub_dt.date()).days > max_post_age_days:
            return False

    return None


def _iso_to_local(iso: Optional[str]) -> str:
    """'2026-11-22T08:30:00+07:00' → '2026-11-22 08:30'."""
    if not iso:
        return ""
    s = str(iso).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


INVITE_KEYWORDS = [
    "mời", "đăng ký", "tham dự", "tham gia", "tổ chức", "khai mạc", "khởi động",
    "tuyển", "chiêu sinh", "hạn chót", "deadline", "link đăng ký", "form",
    "sẽ diễn ra", "dự kiến tổ chức", "thông báo tổ chức", "call for",
]


def is_activity_like(title: str, content: str = "") -> bool:
    """Nội dung có khả năng là HOẠT ĐỘNG sinh viên có thể tham gia?"""
    title_low = re.sub(r"\s+", " ", (title or "").lower())
    if any(k in title_low for k in EXCLUDE_KEYWORDS):
        return False
    body = re.sub(r"\s+", " ", f"{title} {content[:1200]}".lower())
    if not any(k in body for k in ACTIVITY_KEYWORDS):
        return False
    return True


def looks_like_invitation(title: str, content: str = "") -> bool:
    """Bài có lời mời đăng ký/tham dự (dùng để ưu tiên trong UI)."""
    body = re.sub(r"\s+", " ", f"{title} {content[:1200]}".lower())
    return any(k in body for k in INVITE_KEYWORDS)


# ---------------------------------------------------------------------------
# Adapter 1: CTSV JSON API
# ---------------------------------------------------------------------------
class CtsvApiSource:
    """Phòng Công tác Sinh viên – ``/api/news`` (JSON công khai, có phân trang)."""

    key = "ctsv_api"
    name = "Phòng Công tác Sinh viên HCMUS"
    base = "https://ctsv.hcmus.edu.vn"
    api = "https://ctsv.hcmus.edu.vn/api/news"

    def fetch(self, max_pages: int = 2, per_page: int = 50,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None) -> CrawlResult:
        t0 = time.time()
        sess = session or _session()
        posts: list[CrawledPost] = []
        calls = 0
        per_page = max(1, min(100, int(per_page)))
        max_pages = max(1, min(MAX_PAGES_HARD_LIMIT, int(max_pages)))
        try:
            for page in range(1, max_pages + 1):
                if progress:
                    progress(f"CTSV: trang {page}/{max_pages}…")
                r = sess.get(self.api, params={"page": page, "limit": per_page},
                             timeout=REQUEST_TIMEOUT)
                calls += 1
                r.raise_for_status()
                payload = r.json()
                rows = payload.get("data") or []
                if not rows:
                    break
                for row in rows:
                    posts.append(self._to_post(row))
                meta = payload.get("meta") or {}
                if page >= int(meta.get("totalPages") or 1):
                    break
                time.sleep(DEFAULT_DELAY)
            msg = f"Đọc {len(posts)} bài từ API CTSV."
            return CrawlResult(self.key, self.name, True, posts, msg, calls, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(self.key, self.name, False, posts,
                               f"Lỗi gọi API CTSV: {type(exc).__name__}: {exc}",
                               calls, time.time() - t0)

    def _to_post(self, row: dict) -> CrawledPost:
        content_html = row.get("content") or ""
        cat = row.get("category") or {}
        tags = row.get("tags") or []
        return CrawledPost(
            source_key=self.key,
            source_name=self.name,
            source_url=self.base,
            external_id=f"ctsv-{row.get('idCode')}",
            title=_clean(row.get("title")),
            content=html_to_text(content_html),
            url=f"{self.base}/news/{row.get('slug', '')}" if row.get("slug") else self.base,
            published_at=_iso_to_local(row.get("createdAt")),
            organizer=_clean(row.get("author")) or self.name,
            image_url=_clean(row.get("imageUrl")),
            category=_clean(cat.get("name")),
            raw_extra={
                "tags": [_clean(t.get("name")) for t in tags][:6],
                "view_count": row.get("viewCount"),
                "updated_at": row.get("updatedAt"),
                "summary": _clean(row.get("summary")),
            },
        )


# ---------------------------------------------------------------------------
# Adapter 2: HCMUS – The Events Calendar (có start/end/venue)
# ---------------------------------------------------------------------------
class HcmusEventsSource:
    """Trường HCMUS – Lịch sự kiện (The Events Calendar REST API)."""

    key = "hcmus_events"
    name = "Trường HCMUS – Lịch sự kiện"
    base = "https://hcmus.edu.vn"
    api = "https://hcmus.edu.vn/wp-json/tribe/events/v1/events"

    def fetch(self, max_pages: int = 2, per_page: int = 50,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None,
              from_date: str = "2020-01-01",
              until_date: str = "") -> CrawlResult:
        t0 = time.time()
        sess = session or _session()
        posts: list[CrawledPost] = []
        calls = 0
        per_page = max(1, min(50, int(per_page)))
        max_pages = max(1, min(MAX_PAGES_HARD_LIMIT, int(max_pages)))
        try:
            for page in range(1, max_pages + 1):
                if progress:
                    progress(f"Sự kiện HCMUS: trang {page}/{max_pages}…")
                params = {"per_page": per_page, "page": page, "start_date": from_date}
                if until_date:
                    params["end_date"] = until_date
                r = sess.get(self.api, params=params, timeout=REQUEST_TIMEOUT)
                calls += 1
                r.raise_for_status()
                payload = r.json()
                rows = payload.get("events") or []
                if not rows:
                    break
                for row in rows:
                    posts.append(self._to_post(row))
                if page >= int(payload.get("total_pages") or 1):
                    break
                time.sleep(DEFAULT_DELAY)
            msg = f"Đọc {len(posts)} sự kiện (có sẵn ngày/giờ/địa điểm)."
            return CrawlResult(self.key, self.name, True, posts, msg, calls, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(self.key, self.name, False, posts,
                               f"Lỗi gọi API sự kiện: {type(exc).__name__}: {exc}",
                               calls, time.time() - t0)

    def _to_post(self, row: dict) -> CrawledPost:
        venue = row.get("venue") or {}
        orgs = row.get("organizer") or []
        organizer = ""
        if isinstance(orgs, list) and orgs:
            organizer = _clean((orgs[0] or {}).get("organizer"))
        elif isinstance(orgs, dict):
            organizer = _clean(orgs.get("organizer"))
        location_bits = [_clean(venue.get("venue")), _clean(venue.get("address"))]
        location = " – ".join([b for b in location_bits if b])
        start = _iso_to_local(row.get("start_date"))
        end = _iso_to_local(row.get("end_date"))
        return CrawledPost(
            source_key=self.key,
            source_name=self.name,
            source_url=self.base,
            external_id=f"hcmus-ev-{row.get('id')}",
            title=_clean(row.get("title")),
            content=html_to_text(row.get("description") or row.get("excerpt") or ""),
            url=_clean(row.get("url")) or self.base,
            published_at="",
            start_time=start,
            end_time=end,
            location=location,
            organizer=organizer or self.name,
            image_url=_clean(row.get("image", {}).get("url") if isinstance(row.get("image"), dict) else ""),
            category=_clean((row.get("categories") or [{}])[0].get("name"))
            if isinstance(row.get("categories"), list) and row.get("categories") else "",
            raw_extra={"cost": _clean(row.get("cost")), "is_all_day": row.get("all_day")},
        )


# ---------------------------------------------------------------------------
# Adapter 3: HCMUS – bài viết/thông báo (WordPress REST)
# ---------------------------------------------------------------------------
class HcmusPostsSource:
    """Trường HCMUS – Tin tức & Thông báo (WordPress REST API)."""

    key = "hcmus_posts"
    name = "Trường HCMUS – Tin tức/Thông báo"
    base = "https://hcmus.edu.vn"
    api = "https://hcmus.edu.vn/wp-json/wp/v2/posts"

    def fetch(self, max_pages: int = 2, per_page: int = 50,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None) -> CrawlResult:
        t0 = time.time()
        sess = session or _session()
        posts: list[CrawledPost] = []
        calls = 0
        per_page = max(1, min(100, int(per_page)))
        max_pages = max(1, min(MAX_PAGES_HARD_LIMIT, int(max_pages)))
        try:
            for page in range(1, max_pages + 1):
                if progress:
                    progress(f"Tin tức HCMUS: trang {page}/{max_pages}…")
                r = sess.get(self.api, params={"per_page": per_page, "page": page},
                             timeout=REQUEST_TIMEOUT)
                calls += 1
                if r.status_code == 400:
                    break
                r.raise_for_status()
                rows = r.json()
                if not isinstance(rows, list) or not rows:
                    break
                for row in rows:
                    posts.append(self._to_post(row))
                time.sleep(DEFAULT_DELAY)
            msg = f"Đọc {len(posts)} bài viết/thông báo."
            return CrawlResult(self.key, self.name, True, posts, msg, calls, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(self.key, self.name, False, posts,
                               f"Lỗi gọi WP REST: {type(exc).__name__}: {exc}",
                               calls, time.time() - t0)

    def _to_post(self, row: dict) -> CrawledPost:
        title = _clean((row.get("title") or {}).get("rendered"))
        content_html = (row.get("content") or {}).get("rendered", "")
        excerpt_html = (row.get("excerpt") or {}).get("rendered", "")
        return CrawledPost(
            source_key=self.key,
            source_name=self.name,
            source_url=self.base,
            external_id=f"hcmus-post-{row.get('id')}",
            title=title,
            content=html_to_text(content_html) or html_to_text(excerpt_html),
            url=_clean(row.get("link")) or self.base,
            published_at=_iso_to_local(row.get("date")),
            organizer=self.name,
            raw_extra={"modified": row.get("modified"), "slug": row.get("slug")},
        )


# ---------------------------------------------------------------------------
# Adapter 4: Khoa CNTT – trang thông báo HTML
# ---------------------------------------------------------------------------
class FitNewsSource:
    """Khoa Công nghệ Thông tin – trang Thông báo chung (HTML)."""

    key = "fit_news"
    name = "Khoa CNTT HCMUS – Thông báo"
    base = "https://fit.hcmus.edu.vn"
    listing = "https://fit.hcmus.edu.vn/tin-tuc/c/thong-bao-chung"

    def fetch(self, max_pages: int = 1, per_page: int = 30,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None) -> CrawlResult:
        t0 = time.time()
        sess = session or _session()
        calls = 0
        posts: list[CrawledPost] = []
        try:
            if progress:
                progress("Khoa CNTT: đọc trang thông báo…")
            r = sess.get(self.listing, timeout=REQUEST_TIMEOUT)
            calls += 1
            r.raise_for_status()
            posts = self._parse_listing(r.text, limit=per_page, sess=sess)
            msg = f"Đọc {len(posts)} thông báo từ trang Khoa CNTT."
            return CrawlResult(self.key, self.name, True, posts, msg, calls, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(self.key, self.name, False, posts,
                               f"Lỗi đọc trang Khoa CNTT: {type(exc).__name__}: {exc}",
                               calls, time.time() - t0)

    _ITEM_RE = re.compile(
        r'<h6[^>]*>\s*<a[^>]+href="(?P<href>[^"]+)"[^>]*>\s*(?P<title>[\s\S]{3,300}?)\s*</a>\s*</h6>',
        re.I,
    )
    _DATE_RE = re.compile(r'post-date[\s\S]{0,220}?<span>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</span>', re.I)
    _EXCERPT_RE = re.compile(r'</h6>\s*<p[^>]*>([\s\S]{0,600}?)</p>', re.I)

    def _parse_listing(self, page_html: str, limit: int = 30,
                       sess: Optional[requests.Session] = None) -> list[CrawledPost]:
        out: list[CrawledPost] = []
        seen: set[str] = set()
        matches = list(self._ITEM_RE.finditer(page_html))
        for idx, m in enumerate(matches):
            href = _clean(m.group("href"))
            title = html_to_text(m.group("title"))
            if not href or not title or href in seen:
                continue
            seen.add(href)
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else min(
                len(page_html), m.end() + 4000
            )
            chunk = page_html[m.end():end_pos]
            dm = self._DATE_RE.search(chunk)
            published = ""
            if dm:
                try:
                    published = datetime.strptime(dm.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    published = ""
            em = self._EXCERPT_RE.search(chunk)
            excerpt = html_to_text(em.group(1)) if em else ""
            if len(excerpt) < 120 and sess is not None:
                full = self._fetch_detail(sess, urljoin(self.base, href))
                if full:
                    excerpt = full
            out.append(CrawledPost(
                source_key=self.key,
                source_name=self.name,
                source_url=self.base,
                external_id=f"fit-{href.strip('/').replace('/', '-')[:80]}",
                title=title,
                content=excerpt,
                url=urljoin(self.base, href),
                published_at=published,
                organizer="Khoa Công nghệ Thông tin – HCMUS",
            ))
            if len(out) >= limit:
                break
        return out

    def _fetch_detail(self, sess: requests.Session, url: str) -> str:
        """Tải nội dung trang chi tiết của một thông báo FIT."""
        try:
            r = sess.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
        except Exception:  # noqa: BLE001
            return ""
        html = r.text
        for pattern in (
            r'<div[^>]+class="[^"]*(?:post-content|entry-content|content-detail|detail-content)[^"]*"[^>]*>([\s\S]{80,20000}?)</div>',
            r'<article[^>]*>([\s\S]{80,20000}?)</article>',
        ):
            m = re.search(pattern, html, re.I)
            if m:
                text = html_to_text(m.group(1))
                if len(text) > 120:
                    return text[:8000]
        text = html_to_text(html)
        return text[:8000] if len(text) > 200 else ""


# ---------------------------------------------------------------------------
# Adapter 5: Fanpage Facebook qua RSS Feed
# ---------------------------------------------------------------------------
class FacebookRssSource:
    """Đọc bài đăng Fanpage Facebook thông qua RSS Feed trung gian."""

    key = "fb_rss"
    name = "Fanpage Facebook (RSS)"
    feed_urls = [
        "https://rss.app/feeds/Q4esu720qON8jgCm.xml",
    ]

    def fetch(self, max_pages: int = 1, per_page: int = 30,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None) -> CrawlResult:
        t0 = time.time()
        posts: list[CrawledPost] = []
        calls = 0
        try:
            for feed_url in self.feed_urls:
                if progress:
                    progress(f"Facebook RSS: đang đọc {feed_url}…")
                feed = feedparser.parse(feed_url)
                calls += 1
                feed_title = _clean((feed.get("feed") or {}).get("title")) or "Fanpage Facebook"
                for entry in (feed.entries or [])[:per_page]:
                    raw_html = entry.get("summary") or entry.get("description") or ""
                    text_content = html_to_text(raw_html)
                    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
                    title = lines[0][:150] if lines else _clean(entry.get("title"))
                    if not text_content:
                        text_content = title

                    when_info = event_details.extract_when(text_content)

                    posts.append(CrawledPost(
                        source_key=self.key,
                        source_name=self.name,
                        source_url=feed_url,
                        external_id=f"fbrss-{str(entry.get('id') or entry.get('link') or '')[-60:]}",
                        title=title,
                        content=text_content,
                        url=_clean(entry.get("link")),
                        published_at=_clean(entry.get("published")),
                        start_time=when_info.get("start_time") or "",
                        end_time=when_info.get("end_time") or "",
                        organizer=feed_title, 
                    ))
            msg = f"Đọc {len(posts)} bài từ RSS Facebook."
            return CrawlResult(self.key, self.name, True, posts, msg, calls, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(self.key, self.name, False, posts,
                               f"Lỗi đọc RSS Facebook: {type(exc).__name__}: {exc}",
                               calls, time.time() - t0)
# ---------------------------------------------------------------------------
# Facebook – chỉ báo trạng thái, KHÔNG giả vờ thu thập trực tiếp được
# ---------------------------------------------------------------------------
FACEBOOK_NOTE = (
    "Facebook không cho phép đọc bài đăng fanpage trực tiếp khi chưa đăng nhập: mọi request "
    "không kèm cookie đều bị chuyển về trang `facebook.com/login`. Bạn có thể dùng nguồn "
    "**Fanpage Facebook (qua RSS)**, sao chép nội dung vào **Tab 2**, hoặc dùng tiện ích Chrome."
)


def probe_facebook(handle: str = "hcmus.ctsv",
                   session: Optional[requests.Session] = None) -> dict:
    """Kiểm tra TRUNG THỰC xem trang Facebook có đọc được công khai không."""
    sess = session or _session()
    url = f"https://www.facebook.com/{handle.lstrip('@')}"
    try:
        r = sess.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        blocked = "login" in str(r.url) or "checkpoint" in r.text[:4000].lower()
        return {
            "url": url,
            "status_code": r.status_code,
            "final_url": str(r.url),
            "publicly_readable": not blocked,
            "note": FACEBOOK_NOTE if blocked else "Trang trả về nội dung công khai.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status_code": 0, "final_url": "", "publicly_readable": False,
                "note": f"Không kết nối được: {type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Điều phối
# ---------------------------------------------------------------------------
ALL_SOURCES: dict[str, object] = {
    CtsvApiSource.key: CtsvApiSource(),
    HcmusEventsSource.key: HcmusEventsSource(),
    HcmusPostsSource.key: HcmusPostsSource(),
    FitNewsSource.key: FitNewsSource(),
    FacebookRssSource.key: FacebookRssSource(),
}

SOURCE_CHOICES = [
    (key, SOURCE_TYPE_LABELS.get(key, key)) for key in ALL_SOURCES
]


def crawl_all(source_keys: Optional[Iterable[str]] = None,
              max_pages: int = 2,
              per_page: int = 50,
              activity_only: bool = True,
              upcoming_only: bool = True,
              progress: Optional[Callable[[str], None]] = None,
              session: Optional[requests.Session] = None) -> list[CrawlResult]:
    """Chạy lần lượt các nguồn được chọn, trả về kết quả từng nguồn."""
    keys = list(source_keys) if source_keys else list(ALL_SOURCES)
    sess = session or _session()
    results: list[CrawlResult] = []
    for key in keys:
        adapter = ALL_SOURCES.get(key)
        if adapter is None:
            results.append(CrawlResult(key, key, False, [], f"Nguồn '{key}' không tồn tại."))
            continue
        if progress:
            progress(f"▶ Bắt đầu: {SOURCE_TYPE_LABELS.get(key, key)}")
        if isinstance(adapter, (FitNewsSource, FacebookRssSource)):
            res = adapter.fetch(max_pages=1, per_page=per_page, progress=progress, session=sess)
        else:
            res = adapter.fetch(max_pages=max_pages, per_page=per_page,
                                progress=progress, session=sess)
        if activity_only and res.posts:
            before = len(res.posts)
            res.posts = [p for p in res.posts
                         if is_activity_like(p.title, p.content)]
            res.message += f" Giữ lại {len(res.posts)}/{before} bài giống hoạt động."
        if upcoming_only and res.posts:
            before = len(res.posts)
            kept, expired, undated = [], 0, 0
            for post in res.posts:
                verdict = is_upcoming(post.to_record())
                if verdict is False:
                    expired += 1
                else:
                    if verdict is None:
                        undated += 1
                    kept.append(post)
            res.posts = kept
            res.message += (
                f" Bỏ {expired} mục ĐÃ DIỄN RA"
                + (f" (giữ {undated} mục không rõ ngày để bạn tự kiểm tra)" if undated else "")
                + "."
            )
        results.append(res)
        if progress:
            progress(f"✔ Xong: {SOURCE_TYPE_LABELS.get(key, key)} – {res.n} mục")
        time.sleep(DEFAULT_DELAY)
    return results


def crawl_to_records(source_keys: Optional[Iterable[str]] = None,
                     max_pages: int = 2, per_page: int = 50,
                     activity_only: bool = True,
                     upcoming_only: bool = True,
                     progress: Optional[Callable[[str], None]] = None) -> tuple[list[dict], list[dict]]:
    """Tiện dụng: trả về (records, status_rows) cho UI."""
    results = crawl_all(source_keys, max_pages=max_pages, per_page=per_page,
                        activity_only=activity_only, upcoming_only=upcoming_only,
                        progress=progress)
    records: list[dict] = []
    status = []
    for res in results:
        records.extend(p.to_record() for p in res.posts)
        status.append({
            "Nguồn": res.source_name,
            "Trạng thái": "✅ OK" if res.ok else "❌ Lỗi",
            "Số mục": res.n,
            "Thời gian (s)": round(res.elapsed_s, 1),
            "Ghi chú": res.message,
        })
    return records, status


def health_check() -> list[dict]:
    """Kiểm tra nhanh từng nguồn còn sống không (dùng cho nút 'Kiểm tra nguồn')."""
    rows = []
    sess = _session()
    probes = {
        CtsvApiSource.key: ("https://ctsv.hcmus.edu.vn/api/news?page=1&limit=1", "json"),
        HcmusEventsSource.key: ("https://hcmus.edu.vn/wp-json/tribe/events/v1/events"
                                "?per_page=1&start_date=2020-01-01", "json"),
        HcmusPostsSource.key: ("https://hcmus.edu.vn/wp-json/wp/v2/posts?per_page=1", "json"),
        FitNewsSource.key: (FitNewsSource.listing, "html"),
        FacebookRssSource.key: (FacebookRssSource.feed_urls[0], "xml"),
    }
    for key, (url, kind) in probes.items():
        t0 = time.time()
        try:
            r = sess.get(url, timeout=REQUEST_TIMEOUT)
            ok = r.status_code == 200
            detail = ""
            if ok and kind == "json":
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        detail = f"total={data.get('total') or data.get('meta', {}).get('total') or '?'}"
                    elif isinstance(data, list):
                        detail = f"{len(data)} bản ghi"
                except Exception:  # noqa: BLE001
                    detail = "JSON không đọc được"
            elif ok and kind == "xml":
                detail = f"{r.text.count('<item>')} bài RSS"
            elif ok:
                n = len(FitNewsSource._ITEM_RE.findall(r.text))
                detail = f"{n} tiêu đề"
            rows.append({
                "Nguồn": SOURCE_TYPE_LABELS.get(key, key),
                "URL": url.split("?")[0],
                "HTTP": r.status_code,
                "Sống": "✅" if ok else "❌",
                "Chi tiết": detail,
                "ms": int((time.time() - t0) * 1000),
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"Nguồn": SOURCE_TYPE_LABELS.get(key, key),
                         "URL": url.split("?")[0], "HTTP": 0, "Sống": "❌",
                         "Chi tiết": f"{type(exc).__name__}", "ms": 0})
    return rows


# ---------------------------------------------------------------------------
# Ghi vào SQLite (dùng lại đúng pipeline NLP của Tab 2)
# ---------------------------------------------------------------------------
def _get_or_create_source(rec: dict, cache: dict[str, int], db_path=None) -> int:
    """Tìm nguồn theo URL, chưa có thì tạo mới. Trả về source_id."""
    from . import database

    src_url = rec.get("source_url") or ""
    if src_url in cache:
        return cache[src_url]
    sid = database.create_source(
        name=rec.get("source_name") or rec.get("source_key") or "Nguồn công khai",
        url=src_url,
        source_type=rec.get("source_key") or "public_web",
        connection_status="AUTO_CRAWL",
        db_path=db_path,
    )
    cache[src_url] = sid
    return sid


def save_crawled_posts(records: list[dict],
                       db_path=None,
                       progress: Optional[Callable[[str], None]] = None,
                       skip_past: bool = True,
                       require_complete: bool = True) -> dict:
    """Lưu bài thu thập được vào DB qua ĐÚNG pipeline phân tích của Tab 2."""
    from . import database, nlp_engine

    cache: dict[str, int] = {}
    for row in database.get_sources(db_path).to_dict("records"):
        if row.get("url"):
            cache[str(row["url"])] = int(row["id"])

    catalog = [dict(c) for c in database.get_criteria_dict(db_path).values()]

    n_posts = 0
    n_activities = 0
    skipped_past = 0
    expired_skipped: list[str] = []
    incomplete: list[dict] = []
    label_counts: dict[str, int] = {}
    by_source: dict[str, int] = {}
    errors: list[str] = []

    total = len(records)
    for idx, rec in enumerate(records, start=1):
        try:
            if progress and idx % 5 == 1:
                progress(f"Đang lưu & phân tích {idx}/{total}: {str(rec.get('title'))[:46]}…")

            source_id = _get_or_create_source(rec, cache, db_path)
            key = rec.get("source_key") or "?"
            by_source[key] = by_source.get(key, 0) + 1

            title = rec.get("title") or ""
            content = rec.get("content") or ""
            raw_text = (title + "\n\n" + content).strip()

            post_id = database.insert_source_post(
                source_id=source_id,
                raw_text=raw_text,
                url=rec.get("url") or rec.get("source_url") or None,
                fetch_method=f"AUTO_CRAWL:{key}",
                external_post_id=rec.get("external_id") or None,
                published_at=rec.get("published_at") or None,
                is_demo=False,
                db_path=db_path,
            )
            n_posts += 1

            report = nlp_engine.analyze_post(raw_text, url=rec.get("url") or "", criteria_catalog=catalog)
            act = report["activity"]
            flags = report["missing_flags"]

            details = event_details.extract_when(content)

            start_time = (details["start_time"] or rec.get("start_time")
                          or act.get("start_time") or "")
            end_time = (details["end_time"] or rec.get("end_time")
                        or act.get("end_time") or "")
            _loc, _loc_raw = event_details.extract_location(content)
            location = rec.get("location") or _loc or act.get("location") or ""
            organizer = (rec.get("organizer") or act.get("organizer")
                         or rec.get("source_name") or "")
            label = report["relevance_label"]
            label_counts[label] = label_counts.get(label, 0) + 1

            speaker, speaker_raw = event_details.extract_speaker(content)
            duration_min, duration_raw = event_details.extract_duration(content)
            if not duration_min and start_time and end_time:
                if start_time[:10] == end_time[:10]:
                    try:
                        _t0 = datetime.strptime(start_time[:16], "%Y-%m-%d %H:%M")
                        _t1 = datetime.strptime(end_time[:16], "%Y-%m-%d %H:%M")
                        _m = int((_t1 - _t0).total_seconds() // 60)
                        if 0 < _m <= 600:
                            duration_min = _m
                    except ValueError:
                        pass
            registration_deadline = (
                rec.get("registration_deadline") or details["deadline"] or ""
            )

            if skip_past and is_upcoming(
                {"start_time": start_time, "end_time": end_time}
            ) is False:
                expired_skipped.append(title[:80])
                skipped_past += 1
                continue

            _draft = {
                "title": title or act.get("title") or "",
                "start_time": start_time,
                "location": location,
                "organizer": organizer,
            }
            _ok, _missing = event_details.required_report(_draft)
            if require_complete and not _ok:
                incomplete.append({
                    "title": (title or "")[:120],
                    "missing": _missing,
                    "missing_text": ", ".join(
                        event_details.FIELD_LABELS.get(m, m) for m in _missing
                    ),
                    "source": rec.get("source_name") or "",
                    "url": rec.get("url") or "",
                    "has_when_clue": bool(details["start_time"]),
                })
                continue

            database.insert_activity({
                "source_post_id": post_id,
                "parent_activity_id": None,
                "title": (title or act.get("title") or "(không tiêu đề)")[:400],
                "description": content[:4000],
                "organizer": organizer[:300],
                "location": location[:300],
                "campus": nlp_engine.guess_campus(location) if location else "",
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": duration_min,
                "speaker": speaker,
                "start_raw": details["start_raw"] or duration_raw,
                "end_raw": details["end_raw"] or speaker_raw,
                "registration_deadline": registration_deadline,
                "expected_score": act.get("expected_score"),
                "criterion_code": act.get("criterion_code") or "",
                "relevance_label": label,
                "verification_status": report["drl_assessment"].get("status", "UNVERIFIED"),
                "is_missing_time": int(not start_time or flags.get("is_missing_time", 0)),
                "is_missing_location": int(not location or flags.get("is_missing_location", 0)),
                "is_missing_content": int(flags.get("is_missing_content", 0)),
                "is_missing_score": int(flags.get("is_missing_score", 0)),
                "ai_explanation": (
                    ("[MỜI THAM GIA] " if is_activity_like(title, content)
                     and looks_like_invitation(title, content) else "")
                    + report.get("relevance_reason", "")
                ),
                "ai_source": report.get("ai_source", "local_fallback"),
                "is_demo": False,
            }, db_path)
            n_activities += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[{idx}] {type(exc).__name__}: {exc}")

    return {
        "n_posts": n_posts,
        "n_activities": n_activities,
        "skipped_past": skipped_past,
        "incomplete": incomplete,
        "by_label": label_counts,
        "by_source": by_source,
        "errors": errors[:20],
    }