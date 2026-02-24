"""대시보드: Engine 3 NLP 뷰"""
import streamlit as st
import pandas as pd
import json
from pathlib import Path


def render():
    st.title("🧠 Engine 3: NLP Substance Check")
    st.markdown("---")

    # 최근 리포트에서 NLP 결과 읽기
    reports_dir = Path("data/reports")
    if not reports_dir.exists():
        st.info("No reports yet. Run the pipeline first.")
        return

    report_files = sorted(reports_dir.glob("report_*.json"), reverse=True)
    if not report_files:
        st.info("No reports found.")
        return

    # 리포트 선택
    selected = st.selectbox(
        "Select Report",
        report_files,
        format_func=lambda x: x.stem,
    )

    with open(selected, "r", encoding="utf-8") as f:
        report = json.load(f)

    nlp_results = report.get("engine3", {}).get("nlp_results", [])

    if not nlp_results:
        st.warning("No NLP results in this report.")
        return

    st.subheader(f"NLP Analysis ({len(nlp_results)} stocks)")

    df = pd.DataFrame(nlp_results)
    display_cols = ["ticker", "substance_score", "buzz_score", "total_score", "verdict"]
    available = [c for c in display_cols if c in df.columns]

    if available:
        st.dataframe(df[available], use_container_width=True)

    # 개별 종목 상세
    st.subheader("Detail View")
    tickers = [r.get("ticker", "?") for r in nlp_results]
    selected_ticker = st.selectbox("Select Ticker", tickers)

    detail = next((r for r in nlp_results if r.get("ticker") == selected_ticker), None)
    if detail:
        col1, col2, col3 = st.columns(3)
        col1.metric("Substance Score", detail.get("substance_score", "N/A"))
        col2.metric("Buzz Score", detail.get("buzz_score", "N/A"))
        col3.metric("Verdict", detail.get("verdict", "N/A"))

        if detail.get("key_findings"):
            st.write("**Key Findings:**")
            for f in detail["key_findings"]:
                st.write(f"  - {f}")

        if detail.get("summary"):
            st.write("**Summary:**")
            st.write(detail["summary"])
