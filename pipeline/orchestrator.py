"""
통합 파이프라인: 3개 엔진 오케스트레이터
- Engine 1 → Engine 2 → Engine 3 → 종합 리포트
- DB 저장 + 알림 발송
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
from engine1_quant.data_fetcher import get_universe
from engine2_macro.macro_fetcher import MacroFetcher
from engine2_macro.risk_scorer import RiskScorer
from engine2_macro.hedge_allocator import HedgeAllocator
from engine3_nlp.llm_analyzer import LLMAnalyzer
from engine3_nlp.sec_scraper import SECScraper
from storage.db import Database
from alerts.notifier import Notifier


class Orchestrator:
    """3개 엔진 통합 실행 파이프라인"""

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Engine 1
        self.volume_analyzer = VolumeAnalyzer(self.config["engine1"]["surge"])
        self.peak_detector = PeakDetector(self.config["engine1"]["peak"])
        self.neglected_scanner = NeglectedScanner(self.config["engine1"]["neglected"])

        # Engine 2
        self.macro_fetcher = MacroFetcher(self.config["engine2"])
        self.risk_scorer = RiskScorer(self.config["engine2"])
        self.hedge_allocator = HedgeAllocator(self.config["engine2"])

        # Engine 3
        self.llm_analyzer = LLMAnalyzer(self.config["engine3"]["llm"])
        self.sec_scraper = SECScraper(self.config["engine3"]["sec_edgar"])

        # Storage & Alerts
        self.db = Database(config_path)
        self.notifier = Notifier(self.config.get("alerts", {}))

    def _load_tickers(self) -> list[str]:
        """유니버스 자동 로드 (S&P 500 등) + watchlist 병합"""
        universe_name = self.config.get("data", {}).get("universe", "sp500")
        tickers = set(get_universe(universe_name))
        print(f"[Universe] {universe_name}: {len(tickers)} tickers loaded")

        # watchlist.yaml 추가
        watchlist_path = Path("config/watchlist.yaml")
        if watchlist_path.exists():
            with open(watchlist_path, "r", encoding="utf-8") as f:
                wl = yaml.safe_load(f)
            for item in wl.get("watchlist", []):
                tickers.add(item["ticker"])

        # DB watchlist도 추가
        for item in self.db.get_watchlist():
            tickers.add(item["ticker"])

        return sorted(tickers)

    def _load_watchlist_tickers(self) -> set[str]:
        """watchlist 종목만 로드 (NLP 우선 분석 대상)"""
        tickers = set()
        watchlist_path = Path("config/watchlist.yaml")
        if watchlist_path.exists():
            with open(watchlist_path, "r", encoding="utf-8") as f:
                wl = yaml.safe_load(f)
            for item in wl.get("watchlist", []):
                tickers.add(item["ticker"])
        for item in self.db.get_watchlist():
            tickers.add(item["ticker"])
        return tickers

    def run_full_pipeline(self, tickers: list[str] = None) -> dict:
        """전체 파이프라인 실행"""
        if tickers is None:
            tickers = self._load_tickers()

        timestamp = datetime.now().isoformat()
        report = {
            "timestamp": timestamp,
            "universe_size": len(tickers),
            "engine1": {},
            "engine2": {},
            "engine3": {},
            "final_picks": [],
        }

        print(f"\n{'='*60}")
        print(f"  AI Stock Discovery Engine v3.0")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Universe: {len(tickers)} stocks")
        print(f"{'='*60}\n")

        # — Phase 1: 퀀트 필터링 —
        print(f"[Phase 1] 퀀트 필터링 ({len(tickers)} stocks)...")
        print("-" * 40)

        surge_list = self.volume_analyzer.scan_universe(tickers)
        report["engine1"]["surge_stocks"] = surge_list
        print(f"  거래대금 폭증: {len(surge_list)}개 감지")
        for s in surge_list:
            print(f"    {s['ticker']:6s} {s['ratio_5d']}x (5d) | MCap ${s.get('market_cap_b','?')}B")

        peak_warnings = self.peak_detector.scan_universe(tickers, self.volume_analyzer)
        report["engine1"]["peak_warnings"] = peak_warnings
        print(f"  고점 경고: {len(peak_warnings)}개 감지")
        for w in peak_warnings:
            print(f"    {w['ticker']:6s} {w['warning']} | {w['price_pct_of_high']}% of 52w high")

        # DB 저장
        if surge_list:
            self.db.save_scan_results(surge_list, "surge")
        if peak_warnings:
            self.db.save_scan_results(peak_warnings, "peak_warning")

        # — Phase 2: 매크로 체크 —
        print(f"\n[Phase 2] 매크로 리스크 체크...")
        print("-" * 40)

        macro_data = self.macro_fetcher.fetch_all()
        macro_risk = self.risk_scorer.calculate_risk(macro_data)
        report["engine2"] = macro_risk

        print(f"  VIX: {macro_risk.get('vix_current', 'N/A')}")
        print(f"  S&P500 Drawdown: {macro_risk.get('sp500_drawdown', 'N/A')}%")
        print(f"  Risk Score: {macro_risk['risk_score']:.3f}")
        print(f"  Defense Mode: {'ON' if macro_risk['defense_mode'] else 'OFF'}")

        if macro_risk["defense_mode"]:
            for reason in macro_risk.get("defense_reasons", []):
                print(f"    - {reason}")
            allocation = self.hedge_allocator.get_defense_allocation(macro_risk)
            report["engine2"]["hedge_allocation"] = allocation
            print(f"  Defense Ratio: {allocation.get('defense_ratio', 0):.0%}")

        # DB 저장
        self.db.save_macro_snapshot(macro_risk)

        # — Phase 3: NLP 실체 검증 —
        print(f"\n[Phase 3] NLP 실체 검증 (로컬 LLM)...")
        print("-" * 40)

        # 퀀트 필터 통과 종목 + watchlist를 NLP 검증 대상으로
        surge_tickers = {s["ticker"] for s in surge_list}
        peak_tickers = {w["ticker"] for w in peak_warnings}
        watchlist_tickers = self._load_watchlist_tickers()
        nlp_candidates = sorted(surge_tickers | peak_tickers | watchlist_tickers)

        if not nlp_candidates:
            nlp_candidates = tickers[:10]
            print(f"  (필터 통과 종목 없음 — 상위 {len(nlp_candidates)}개 분석)")
        else:
            print(f"  NLP 대상: {len(nlp_candidates)}개 (폭증 {len(surge_tickers)} + 고점경고 {len(peak_tickers)} + watchlist {len(watchlist_tickers)})")

        nlp_results = []
        for ticker in nlp_candidates:
            print(f"  분석 중: {ticker}...", end=" ")
            filing = self.sec_scraper.get_latest_filing(ticker)

            if filing:
                result = self.llm_analyzer.analyze_filing(
                    ticker, filing["type"], filing["text"]
                )
                if result:
                    nlp_results.append({"ticker": ticker, **result})
                    score = result.get("substance_score", "?")
                    print(f"Score: {score}")
                else:
                    print("LLM unavailable")
            else:
                print("No filing")

        report["engine3"]["nlp_results"] = nlp_results

        # DB 저장
        if nlp_results:
            self.db.save_nlp_analysis(nlp_results)

        # — 종합 점수 산출 —
        print(f"\n[Final] 종합 점수 산출...")
        print("-" * 40)

        # NLP 분석된 종목만 최종 점수 대상
        nlp_analyzed = {r.get("ticker") for r in nlp_results}
        surge_map = {s["ticker"]: s for s in surge_list}
        score_targets = []
        for ticker in nlp_analyzed:
            if ticker in surge_map:
                score_targets.append(surge_map[ticker])
            else:
                score_targets.append({"ticker": ticker, "ratio_5d": 1.0})

        if not score_targets:
            score_targets = [{"ticker": t, "ratio_5d": 1.0} for t in nlp_candidates[:10]]

        weights = self.config["scoring"]["weights"]
        final_picks = self._calculate_final_scores(
            score_targets, macro_risk, nlp_results, weights
        )
        report["final_picks"] = final_picks

        # 결과 출력
        print(f"\n{'='*60}")
        print(f"  FINAL RESULTS ({len(final_picks)} stocks)")
        print(f"{'='*60}")
        for pick in final_picks:
            print(f"  {pick['signal']:12s} | {pick['ticker']:6s} | "
                  f"Total: {pick['total_score']:.3f} "
                  f"(Q:{pick['quant_score']:.2f} M:{pick['macro_score']:.2f} N:{pick['nlp_score']:.2f})")

        # DB 저장
        if final_picks:
            self.db.save_final_report(final_picks)

        # 리포트 JSON 저장
        self._save_report(report)

        # 알림 발송
        message = self.notifier.format_report(report)
        self.notifier.send(message)

        return report

    def run_quant_only(self, tickers: list[str] = None) -> dict:
        """Engine 1만 실행"""
        if tickers is None:
            tickers = self._load_tickers()

        print(f"[Quant Only] Scanning {len(tickers)} stocks...")
        surge = self.volume_analyzer.scan_universe(tickers)
        peaks = self.peak_detector.scan_universe(tickers, self.volume_analyzer)

        if surge:
            self.db.save_scan_results(surge, "surge")
        if peaks:
            self.db.save_scan_results(peaks, "peak_warning")

        return {"surge": surge, "peak_warnings": peaks}

    def _calculate_final_scores(self, score_targets, macro, nlp_results, weights):
        """종합 점수 계산"""
        nlp_map = {r.get("ticker"): r.get("substance_score", 0) for r in nlp_results}

        results = []
        for stock in score_targets:
            ticker = stock["ticker"]

            quant_raw = min(stock.get("ratio_5d", 1.0) / 10, 1.0)
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

    parser = argparse.ArgumentParser(description="AI Stock Discovery Engine v3.0")
    parser.add_argument("--mode", choices=["full", "quant", "nlp"], default="full")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--tickers", nargs="*", help="Custom ticker list")
    args = parser.parse_args()

    orchestrator = Orchestrator(args.config)

    if args.mode == "full":
        report = orchestrator.run_full_pipeline(args.tickers)
    elif args.mode == "quant":
        result = orchestrator.run_quant_only(args.tickers)
        print(json.dumps(result, indent=2, default=str))
