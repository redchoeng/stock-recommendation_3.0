"""
통합 파이프라인: 3개 엔진 오케스트레이터
- 매일 시장 마감 후 자동 실행
- Engine 1 → Engine 2 → Engine 3 → 종합 리포트
"""
import yaml
import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine1_quant.volume_analyzer import VolumeAnalyzer
from engine1_quant.peak_detector import PeakDetector
from engine1_quant.neglected_scanner import NeglectedScanner
from engine2_macro.macro_fetcher import MacroFetcher
from engine2_macro.risk_scorer import RiskScorer
from engine3_nlp.llm_analyzer import LLMAnalyzer
from engine3_nlp.sec_scraper import SECScraper


class Orchestrator:
    """3개 엔진 통합 실행 파이프라인"""

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Engine 1 초기화
        self.volume_analyzer = VolumeAnalyzer(self.config["engine1"]["surge"])
        self.peak_detector = PeakDetector(self.config["engine1"]["peak"])
        self.neglected_scanner = NeglectedScanner(self.config["engine1"]["neglected"])

        # Engine 2 초기화
        self.macro_fetcher = MacroFetcher(self.config["engine2"])
        self.risk_scorer = RiskScorer(self.config["engine2"])

        # Engine 3 초기화
        self.llm_analyzer = LLMAnalyzer(self.config["engine3"]["llm"])
        self.sec_scraper = SECScraper(self.config["engine3"]["sec_edgar"])

    def run_full_pipeline(self, tickers: list[str]) -> dict:
        """전체 파이프라인 실행"""
        timestamp = datetime.now().isoformat()
        report = {
            "timestamp": timestamp,
            "universe_size": len(tickers),
            "engine1": {},
            "engine2": {},
            "engine3": {},
            "final_picks": [],
        }

        # — Phase 1: 퀀트 필터링 —
        print("=" * 60)
        print("[Phase 1] 퀀트 필터링 시작...")
        print("=" * 60)

        surge_list = self.volume_analyzer.scan_universe(tickers)
        report["engine1"]["surge_stocks"] = surge_list
        print(f"  거래대금 폭증: {len(surge_list)}개 감지")

        peak_warnings = self.peak_detector.scan_universe(tickers, self.volume_analyzer)
        report["engine1"]["peak_warnings"] = peak_warnings
        print(f"  고점 경고: {len(peak_warnings)}개 감지")

        # — Phase 2: 매크로 체크 —
        print("\n" + "=" * 60)
        print("[Phase 2] 매크로 리스크 체크...")
        print("=" * 60)

        macro_data = self.macro_fetcher.fetch_all()
        macro_risk = self.risk_scorer.calculate_risk(macro_data)
        report["engine2"] = macro_risk
        print(f"  리스크 점수: {macro_risk['risk_score']:.2f} "
              f"(방어모드: {macro_risk['defense_mode']})")

        # — Phase 3: NLP 실체 검증 —
        print("\n" + "=" * 60)
        print("[Phase 3] NLP 실체 검증 (로컬 LLM)...")
        print("=" * 60)

        nlp_candidates = [s["ticker"] for s in surge_list]
        nlp_results = []

        for ticker in nlp_candidates:
            print(f"  분석 중: {ticker}")
            filing = self.sec_scraper.get_latest_filing(ticker)

            if filing:
                result = self.llm_analyzer.analyze_filing(
                    ticker, filing["type"], filing["text"]
                )
                if result:
                    nlp_results.append({"ticker": ticker, **result})
            else:
                print(f"    [SKIP] {ticker}: SEC filing 없음")

        report["engine3"]["nlp_results"] = nlp_results

        # — 종합 점수 산출 —
        print("\n" + "=" * 60)
        print("[Final] 종합 점수 산출...")
        print("=" * 60)

        weights = self.config["scoring"]["weights"]
        final_picks = self._calculate_final_scores(
            surge_list, macro_risk, nlp_results, weights
        )
        report["final_picks"] = final_picks

        for pick in final_picks:
            print(f"  {pick['signal']} | {pick['ticker']}: "
                  f"총점 {pick['total_score']:.2f} "
                  f"(퀀트:{pick['quant_score']:.2f} "
                  f"매크로:{pick['macro_score']:.2f} "
                  f"NLP:{pick['nlp_score']:.2f})")

        self._save_report(report)
        return report

    def _calculate_final_scores(self, surge_list, macro, nlp_results, weights):
        """종합 점수 계산"""
        nlp_map = {r.get("ticker"): r.get("substance_score", 0) for r in nlp_results}

        results = []
        for stock in surge_list:
            ticker = stock["ticker"]

            quant_raw = min(stock.get("ratio_5d", 0) / 10, 1.0)
            macro_raw = 1 - macro.get("risk_score", 0.5)
            nlp_raw = nlp_map.get(ticker, 5) / 10

            total = (
                quant_raw * weights["quant"]
                + macro_raw * weights["macro"]
                + nlp_raw * weights["nlp"]
            )

            thresholds = self.config["scoring"]["signals"]
            if total >= thresholds["strong_buy"]:
                signal = "STRONG_BUY"
            elif total >= thresholds["buy"]:
                signal = "BUY"
            elif total >= thresholds["hold"]:
                signal = "HOLD"
            elif total >= thresholds["sell"]:
                signal = "SELL"
            else:
                signal = "AVOID"

            results.append({
                "ticker": ticker,
                "quant_score": round(quant_raw, 3),
                "macro_score": round(macro_raw, 3),
                "nlp_score": round(nlp_raw, 3),
                "total_score": round(total, 3),
                "signal": signal,
            })

        results.sort(key=lambda x: x["total_score"], reverse=True)
        return results

    def _save_report(self, report: dict):
        """리포트 JSON 저장"""
        output_dir = Path("data/reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"report_{date_str}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nReport saved: {filepath}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Stock Discovery Engine")
    parser.add_argument("--mode", choices=["full", "quant", "nlp"], default="full")
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    TEST_TICKERS = [
        "NVDA", "AVGO", "TER", "NFLX", "V", "MA",
        "AAPL", "MSFT", "TSLA", "AMD", "GOOGL", "META",
        "AMZN", "CRM", "PLTR", "IONQ", "RGTI",
    ]

    orchestrator = Orchestrator(args.config)

    if args.mode == "full":
        report = orchestrator.run_full_pipeline(TEST_TICKERS)
    elif args.mode == "quant":
        surge = orchestrator.volume_analyzer.scan_universe(TEST_TICKERS)
        print(json.dumps(surge, indent=2))
