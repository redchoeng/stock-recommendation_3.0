"""
Streamlit 대시보드 메인
- 최종 리포트, 퀀트 뷰, 매크로 뷰, NLP 뷰
"""
import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="AI Stock Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 사이드바 네비게이션
page = st.sidebar.selectbox(
    "Navigation",
    ["Overview", "Quant (Engine 1)", "Macro (Engine 2)", "NLP (Engine 3)", "Watchlist"],
)

if page == "Overview":
    from dashboard.pages.overview import render
    render()
elif page == "Quant (Engine 1)":
    from dashboard.pages.quant_view import render
    render()
elif page == "Macro (Engine 2)":
    from dashboard.pages.macro_view import render
    render()
elif page == "NLP (Engine 3)":
    from dashboard.pages.nlp_view import render
    render()
elif page == "Watchlist":
    from dashboard.pages.watchlist_view import render
    render()
