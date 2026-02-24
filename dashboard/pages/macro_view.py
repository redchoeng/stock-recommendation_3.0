"""대시보드: Engine 2 매크로 뷰"""
import streamlit as st
import pandas as pd
from storage.db import Database


def render():
    st.title("🌡️ Engine 2: Macro & Hedge")
    st.markdown("---")

    db = Database()
    history = db.get_macro_history(days=90)

    if not history:
        st.info("No macro data yet. Run the pipeline first.")
        return

    latest = history[0]

    # 현재 상태
    col1, col2, col3 = st.columns(3)
    col1.metric("Risk Score", f"{latest['risk_score']:.2f}")
    col2.metric("VIX", latest.get("vix", "N/A"))
    col3.metric(
        "Defense Mode",
        "ON ⚠️" if latest.get("defense_mode") else "OFF ✅",
    )

    # 리스크 점수 추이
    st.subheader("Risk Score Trend (90 days)")
    if len(history) > 1:
        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        st.line_chart(df.set_index("date")[["risk_score"]])

        # VIX 추이
        if "vix" in df.columns:
            st.subheader("VIX Trend")
            st.line_chart(df.set_index("date")[["vix"]])
