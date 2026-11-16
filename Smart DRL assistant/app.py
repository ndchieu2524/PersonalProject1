"""SMART DRL ASSISTANT – HCMUS (MVP)

Chạy:
    streamlit run app.py

Ứng dụng gồm 7 tab:
    1. Dashboard & Đồng bộ Plugin (Portal CTĐB & hcmus.drl.vn)
    2. Thu thập TỰ ĐỘNG từ cổng công khai HCMUS (API + HTML)
    3. Thu thập & Bóc tách Bài đăng OSA thủ công (dán link/nội dung)
    4. Kho Hoạt động & Cảnh báo Dữ liệu Khuyết
    5. Lộ trình ĐRL Tối ưu & Kiểm tra Trùng Lịch học (NetworkX)
    6. Quản lý Quy chế ĐRL (hcmus.drl.vn)
    7. Thực nghiệm & Đánh giá Mô hình Học máy

Toàn bộ dữ liệu mẫu mang nhãn [DEMO]. Không lưu mật khẩu cổng trường.
"""
from __future__ import annotations

import streamlit as st

from drl import __app_name__, __version__
from drl import ui_common as ui
from drl import (ui_sidebar, ui_tab_crawler, ui_tab1_dashboard, ui_tab2_ingest,
                 ui_tab3_explorer, ui_tab4_pathway, ui_tab5_criteria, ui_tab6_ml)

st.set_page_config(
    page_title=f"{__app_name__} – MVP",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Khởi tạo DB + seed [DEMO] nếu trống (chạy 1 lần / phiên)
ui.ensure_demo_seed()
ui.inject_css()
ui_sidebar.render()

TABS = [
    ("📊 Tổng quan & Đồng bộ", ui_tab1_dashboard.render),
    ("🌐 Thu thập TỰ ĐỘNG", ui_tab_crawler.render),
    ("📥 Thu thập OSA (thủ công)", ui_tab2_ingest.render),
    ("🗂️ Kho hoạt động", ui_tab3_explorer.render),
    ("🧭 Lộ trình tối ưu", ui_tab4_pathway.render),
    ("📜 Quy chế ĐRL", ui_tab5_criteria.render),
    ("🧪 Đánh giá ML", ui_tab6_ml.render),
]

tab_objects = st.tabs([name for name, _ in TABS])
for tab_obj, (_, render_fn) in zip(tab_objects, TABS):
    with tab_obj:
        try:
            render_fn()
        except Exception as exc:  # noqa: BLE001
            st.error(
                "Đã xảy ra lỗi khi hiển thị tab này. Ứng dụng vẫn tiếp tục chạy các tab khác.\n\n"
                f"`{type(exc).__name__}: {exc}`"
            )
            with st.expander("Chi tiết kỹ thuật (dành cho nhóm phát triển)"):
                import traceback

                st.code(traceback.format_exc(), language="text")

ui.footer()
st.caption(f"Smart DRL Assistant HCMUS · {__version__} · Dữ liệu mẫu được gắn nhãn [DEMO] rõ ràng.")
