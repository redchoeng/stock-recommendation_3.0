"""
Engine 1-C: 소외주 스캐너 (비자/마스터카드 발굴 로직)
- 시총 상위 대형주 중 거래대금 지속 하락 → 소외주 리스트
"""
import pandas as pd
import numpy as np
from scipy.stats import linregress
from typing import Optional
import yfinance as yf


class NeglectedScanner:
    """시총 상위 대형주 중 거래대금 하락 추세 감지"""

    def __init__(self, config: dict):
        self.top_n = config.get("top_n_by_market_cap", 100)
        self.slope_window = config.get("slope_window_days", 60)
        self.slope_threshold = config.get("slope_threshold", -0.02)

    def detect_neglected(self, df: pd.DataFrame, ticker: str) -> Optional[dict]:
        """
        소외주 감지 (Filter 1-C)
        조건: 시총 상위 대형주인데 거래대금이 지속 하락 (음의 기울기)
        """
        if df is None or len(df) < self.slope_window:
            return None

        # 최근 N일 거래대금으로 회귀분석
        recent_tv = df["trade_value"].tail(self.slope_window).values
        days = np.arange(len(recent_tv))

        # 정규화 (시작점 = 1.0)
        if recent_tv[0] == 0:
            return None
        normalized = recent_tv / recent_tv[0]

        slope, intercept, r_value, p_value, std_err = linregress(days, normalized)

        if slope >= self.slope_threshold:
            return None  # 하락 추세가 아님

        # 현재 거래대금 vs 60일 전 대비
        tv_change_pct = (recent_tv[-1] / recent_tv[0] - 1) * 100

        return {
            "ticker": ticker,
            "slope": round(slope, 5),
            "r_squared": round(r_value ** 2, 3),
            "tv_change_pct": round(tv_change_pct, 1),
            "current_tv": round(float(recent_tv[-1]), 0),
            "signal": "DEEP_NEGLECT" if slope < self.slope_threshold * 2 else "NEGLECTED",
        }

    def get_top_market_cap_tickers(self) -> list[str]:
        """S&P 500에서 시총 상위 N개 추출 (간이 방식)"""
        # 실제로는 외부 데이터 소스에서 가져와야 하지만,
        # 여기서는 하드코딩된 주요 대형주 사용
        sp500_top = [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY",
            "AVGO", "JPM", "TSLA", "V", "UNH", "MA", "XOM", "COST", "HD",
            "PG", "JNJ", "NFLX", "ABBV", "CRM", "BAC", "AMD", "CVX", "KO",
            "MRK", "PEP", "TMO", "LIN", "WMT", "CSCO", "ACN", "ADBE", "MCD",
            "ABT", "DHR", "PM", "TXN", "NEE", "DIS", "INTC", "CMCSA", "VZ",
            "PFE", "WFC", "IBM", "AMGN", "GE", "CAT",
        ]
        return sp500_top[:self.top_n]

    def scan(self, volume_analyzer, tickers: list[str] = None) -> list[dict]:
        """소외주 스캔 실행"""
        if tickers is None:
            tickers = self.get_top_market_cap_tickers()

        results = []

        for ticker in tickers:
            df = volume_analyzer.fetch_data(ticker)
            if df is None:
                continue

            result = self.detect_neglected(df, ticker)
            if result:
                results.append(result)

        # 기울기 낮은 순 (가장 소외된 순)
        results.sort(key=lambda x: x["slope"])
        return results


if __name__ == "__main__":
    from volume_analyzer import VolumeAnalyzer

    va_config = {"avg_period_days": 252, "surge_multiplier": 3.0, "min_market_cap_b": 5}
    va = VolumeAnalyzer(va_config)

    ns_config = {"top_n_by_market_cap": 50, "slope_window_days": 60, "slope_threshold": -0.02}
    scanner = NeglectedScanner(ns_config)

    neglected = scanner.scan(va)
    print(f"소외주 ({len(neglected)}개):")
    for n in neglected:
        print(f"  {n['ticker']}: {n['signal']} "
              f"(기울기 {n['slope']}, 변동 {n['tv_change_pct']}%)")
