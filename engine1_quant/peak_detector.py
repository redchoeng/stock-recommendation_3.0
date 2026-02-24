"""
Engine 1-B: 고점 경고 (넷플릭스 로직)
- 주가 52주 고점 부근 + 거래대금 이동평균 하향 이탈 → 매도 경고
"""
import pandas as pd
import numpy as np
from typing import Optional
import yfinance as yf


class PeakDetector:
    """52주 고점 부근에서 거래대금 이탈 감지"""

    def __init__(self, config: dict):
        self.high_threshold = config.get("high_threshold", 0.95)
        self.ma_short = config.get("ma_short", 20)
        self.ma_long = config.get("ma_long", 60)

    def detect_peak_warning(self, df: pd.DataFrame, ticker: str) -> Optional[dict]:
        """
        고점 경고 감지 (Filter 1-B)
        조건: 주가가 52주 고점의 95% 이상 + 거래대금 MA20 < MA60 (데드크로스)
        """
        if df is None or len(df) < 252:
            return None

        current_price = float(df["Close"].iloc[-1])
        high_52w = float(df["Close"].tail(252).max())

        # 52주 고점 부근인지
        if current_price < high_52w * self.high_threshold:
            return None

        # 거래대금 이동평균 데드크로스 확인
        tv_ma_short = float(df["trade_value"].rolling(self.ma_short).mean().iloc[-1])
        tv_ma_long = float(df["trade_value"].rolling(self.ma_long).mean().iloc[-1])

        if np.isnan(tv_ma_short) or np.isnan(tv_ma_long) or tv_ma_long == 0:
            return None

        if tv_ma_short >= tv_ma_long:
            return None

        # 거래대금 감소율
        tv_ratio = tv_ma_short / tv_ma_long

        return {
            "ticker": ticker,
            "current_price": round(float(current_price), 2),
            "high_52w": round(float(high_52w), 2),
            "price_pct_of_high": round(float(current_price / high_52w * 100), 1),
            "tv_ma_short": round(float(tv_ma_short), 0),
            "tv_ma_long": round(float(tv_ma_long), 0),
            "tv_ratio": round(float(tv_ratio), 3),
            "warning": "HIGH_RISK" if tv_ratio < 0.7 else "CAUTION",
        }

    def scan_universe(self, tickers: list[str], volume_analyzer) -> list[dict]:
        """전체 유니버스에서 고점 경고 종목 스캔"""
        warnings = []

        for ticker in tickers:
            df = volume_analyzer.fetch_data(ticker)
            if df is None:
                continue

            result = self.detect_peak_warning(df, ticker)
            if result:
                warnings.append(result)

        warnings.sort(key=lambda x: x["tv_ratio"])
        return warnings


if __name__ == "__main__":
    from volume_analyzer import VolumeAnalyzer

    va_config = {"avg_period_days": 252, "surge_multiplier": 3.0, "min_market_cap_b": 5}
    va = VolumeAnalyzer(va_config)

    pd_config = {"high_threshold": 0.95, "ma_short": 20, "ma_long": 60}
    detector = PeakDetector(pd_config)

    test_tickers = ["NFLX", "AAPL", "MSFT", "NVDA", "TSLA"]
    warnings = detector.scan_universe(test_tickers, va)
    print(f"고점 경고 종목 ({len(warnings)}개):")
    for w in warnings:
        print(f"  {w['ticker']}: {w['warning']} "
              f"(고점 대비 {w['price_pct_of_high']}%, "
              f"거래대금 비율 {w['tv_ratio']})")
