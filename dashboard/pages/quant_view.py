"""대시보드: Engine 1 퀀트 뷰"""
import streamlit as st
import pandas as pd
from storage.db import Database


def render():
    st.title("📈 Engine 1: Quant Filter")
    st.markdown("---")

    db = Database()

    tab1, tab2, tab3 = st.tabs(["Volume Surge", "Peak Warning", "Neglected"])

    with tab1:
        st.subheader("거래대금 폭증 종목")
        data = db.get_recent_scans("surge", days=7)
        if data:
            df = pd.DataFrame(data)
            display_cols = ["ticker", "ratio_1d", "ratio_5d", "market_cap_b"]
            available = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available], use_container_width=True)
        else:
            st.info("No surge data. Run Engine 1 first.")

    with tab2:
        st.subheader("고점 경고 종목")
        data = db.get_recent_scans("peak_warning", days=7)
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No peak warnings.")

    with tab3:
        st.subheader("소외주 리스트")
        data = db.get_recent_scans("neglected", days=7)
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No neglected stocks detected.")
