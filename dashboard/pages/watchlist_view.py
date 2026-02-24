"""대시보드: 감시 종목 관리"""
import streamlit as st
import pandas as pd
from storage.db import Database


def render():
    st.title("👀 Watchlist")
    st.markdown("---")

    db = Database()

    # 종목 추가
    with st.expander("Add to Watchlist"):
        col1, col2 = st.columns(2)
        ticker = col1.text_input("Ticker", placeholder="NVDA")
        name = col2.text_input("Company Name", placeholder="NVIDIA")
        reason = st.text_input("Reason", placeholder="Volume surge detected")

        if st.button("Add"):
            if ticker:
                db.add_to_watchlist(ticker.upper(), name, reason)
                st.success(f"{ticker.upper()} added to watchlist")
                st.rerun()

    # 현재 감시 종목
    watchlist = db.get_watchlist()
    if watchlist:
        df = pd.DataFrame(watchlist)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Watchlist is empty. Add some tickers above.")
