"""대시보드: 종합 Overview"""
import streamlit as st
import pandas as pd
from storage.db import Database


def render():
    st.title("📊 AI Stock Discovery Engine")
    st.markdown("---")

    db = Database()

    # 최신 리포트
    st.header("Latest Report")
    report = db.get_latest_report()

    if not report:
        st.info("No reports yet. Run the pipeline first: `python -m pipeline.orchestrator`")
        return

    df = pd.DataFrame(report)

    # 시그널별 색상
    def color_signal(val):
        colors = {
            "STRONG_BUY": "background-color: #00c853",
            "BUY": "background-color: #2196f3",
            "HOLD": "background-color: #ffc107",
            "SELL": "background-color: #ff9800",
            "AVOID": "background-color: #f44336",
        }
        return colors.get(val, "")

    st.dataframe(
        df.style.applymap(color_signal, subset=["signal"]),
        use_container_width=True,
    )

    # 요약 메트릭
    col1, col2, col3, col4 = st.columns(4)
    buys = len([r for r in report if r["signal"] in ("STRONG_BUY", "BUY")])
    holds = len([r for r in report if r["signal"] == "HOLD"])
    sells = len([r for r in report if r["signal"] in ("SELL", "AVOID")])

    col1.metric("Total Picks", len(report))
    col2.metric("Buy Signals", buys)
    col3.metric("Hold", holds)
    col4.metric("Sell/Avoid", sells)

    # 매크로 상태
    st.header("Macro Status")
    macro_history = db.get_macro_history(days=30)

    if macro_history:
        latest_macro = macro_history[0]
        mcol1, mcol2 = st.columns(2)
        mcol1.metric("Risk Score", f"{latest_macro['risk_score']:.2f}")
        mcol2.metric("VIX", latest_macro.get("vix", "N/A"))

        if latest_macro.get("defense_mode"):
            st.warning("⚠️ Defense Mode Active")

        if len(macro_history) > 1:
            macro_df = pd.DataFrame(macro_history)
            macro_df["date"] = pd.to_datetime(macro_df["date"])
            st.line_chart(macro_df.set_index("date")["risk_score"])
    else:
        st.info("No macro data yet.")
