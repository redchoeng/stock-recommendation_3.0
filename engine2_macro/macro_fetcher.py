"""
Engine 2: 매크로 데이터 수집
- FRED API: CPI, 실업률, 기준금리, 국채금리
- yfinance: VIX, S&P 500
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False


class MacroFetcher:
    """매크로 경제 지표 수집"""

    def __init__(self, config: dict):
        self.fred_series = config.get("fred_series", {})
        self.vix_ticker = config.get("vix_ticker", "^VIX")

        api_key = os.environ.get("FRED_API_KEY", "")
        if FRED_AVAILABLE and api_key:
            self.fred = Fred(api_key=api_key)
        else:
            self.fred = None
            if not FRED_AVAILABLE:
                print("[WARN] fredapi not installed. Install with: pip install fredapi")
            elif not api_key:
                print("[WARN] FRED_API_KEY not set. Macro data will use fallback values.")

    def fetch_fred_series(self, series_id: str, months: int = 12) -> Optional[pd.Series]:
        """FRED 시리즈 데이터 가져오기"""
        if not self.fred:
            return None

        try:
            end = datetime.now()
            start = end - timedelta(days=months * 31)
            data = self.fred.get_series(series_id, start, end)
            return data.dropna()
        except Exception as e:
            print(f"[FRED ERROR] {series_id}: {e}")
            return None

    def fetch_vix(self) -> dict:
        """VIX 현재값 및 추세"""
        try:
            df = yf.download(self.vix_ticker, period="3mo", progress=False)
            if df.empty:
                return {"current": None, "ma_20": None}

            current = float(df["Close"].iloc[-1])
            ma_20 = float(df["Close"].rolling(20).mean().iloc[-1])

            return {
                "current": round(current, 2),
                "ma_20": round(ma_20, 2),
                "trend": "rising" if current > ma_20 else "falling",
            }
        except Exception as e:
            print(f"[VIX ERROR] {e}")
            return {"current": None, "ma_20": None}

    def fetch_sp500(self) -> dict:
        """S&P 500 현재 상태 (고점 대비 하락률)"""
        try:
            df = yf.download("^GSPC", period="1y", progress=False)
            if df.empty:
                return {"current": None, "drawdown_pct": None}

            current = float(df["Close"].iloc[-1])
            high_52w = float(df["Close"].max())
            drawdown = (current / high_52w - 1) * 100

            return {
                "current": round(current, 2),
                "high_52w": round(high_52w, 2),
                "drawdown_pct": round(drawdown, 2),
            }
        except Exception as e:
            print(f"[SP500 ERROR] {e}")
            return {"current": None, "drawdown_pct": None}

    def fetch_all(self) -> dict:
        """전체 매크로 데이터 수집"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "vix": self.fetch_vix(),
            "sp500": self.fetch_sp500(),
            "fred": {},
        }

        # FRED 데이터 수집
        for name, series_id in self.fred_series.items():
            series = self.fetch_fred_series(series_id)
            if series is not None and len(series) >= 2:
                current = float(series.iloc[-1])
                previous = float(series.iloc[-2])
                change = current - previous
                result["fred"][name] = {
                    "current": round(current, 4),
                    "previous": round(previous, 4),
                    "change": round(change, 4),
                }
            else:
                result["fred"][name] = {"current": None, "previous": None, "change": None}

        return result


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    config = {
        "fred_series": {
            "cpi": "CPIAUCSL",
            "unemployment": "UNRATE",
            "fed_rate": "FEDFUNDS",
            "yield_10y": "DGS10",
            "yield_2y": "DGS2",
        },
        "vix_ticker": "^VIX",
    }

    fetcher = MacroFetcher(config)
    data = fetcher.fetch_all()

    import json
    print(json.dumps(data, indent=2, default=str))
