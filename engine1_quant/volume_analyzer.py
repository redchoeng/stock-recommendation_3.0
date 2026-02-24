"""
Engine 1-A: 거래대금 폭증 감지 (엔비디아/브로드컴 발굴 로직)
- 과거 1년 평균 거래대금 대비 N배 이상 급증한 종목 필터링
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import yfinance as yf


class VolumeAnalyzer:
    """거래대금(주가 × 거래량) 기반 종목 필터링"""

    def __init__(self, config: dict):
        self.avg_period = config.get("avg_period_days", 252)
        self.surge_multiplier = config.get("surge_multiplier", 3.0)
        self.min_market_cap_b = config.get("min_market_cap_b", 5)

    def fetch_data(self, ticker: str, period_days: int = 504) -> Optional[pd.DataFrame]:
        """yfinance로 일봉 데이터 수집 & 거래대금 계산"""
        try:
            end = datetime.now()
            start = end - timedelta(days=int(period_days * 1.5))  # 영업일 보정
            df = yf.download(ticker, start=start, end=end, progress=False)

            # yfinance MultiIndex 컬럼 평탄화
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df.empty or len(df) < self.avg_period:
                return None

            # 거래대금 = 종가 × 거래량
            df["trade_value"] = df["Close"] * df["Volume"]

            # 이동평균
            df["tv_ma_20"] = df["trade_value"].rolling(20).mean()
            df["tv_ma_60"] = df["trade_value"].rolling(60).mean()
            df["tv_ma_1y"] = df["trade_value"].rolling(self.avg_period).mean()

            return df
        except Exception as e:
            print(f"[ERROR] {ticker} 데이터 수집 실패: {e}")
            return None

    def detect_surge(self, df: pd.DataFrame) -> dict:
        """
        거래대금 폭증 감지 (Filter 1-A)
        - 과거 1년 평균 거래대금 대비 최근 거래대금 비율 계산
        """
        if df is None or df.empty:
            return {"surge": False, "ratio": 0}

        latest_tv = float(df["trade_value"].iloc[-1])
        avg_tv_1y = float(df["tv_ma_1y"].iloc[-1])

        if avg_tv_1y == 0 or np.isnan(avg_tv_1y):
            return {"surge": False, "ratio": 0}

        ratio = latest_tv / avg_tv_1y

        # 최근 5일 평균으로도 체크 (1일 이상치 방지)
        recent_5d_avg = float(df["trade_value"].tail(5).mean())
        ratio_5d = recent_5d_avg / avg_tv_1y

        return {
            "surge": ratio >= self.surge_multiplier,
            "ratio_1d": round(ratio, 2),
            "ratio_5d": round(ratio_5d, 2),
            "latest_trade_value": round(latest_tv, 0),
            "avg_trade_value_1y": round(avg_tv_1y, 0),
        }

    def scan_universe(self, tickers: list[str]) -> list[dict]:
        """전체 유니버스 스캔 → 거래대금 폭증 종목 리스트 반환"""
        results = []

        for ticker in tickers:
            df = self.fetch_data(ticker)
            if df is None:
                continue

            surge_info = self.detect_surge(df)

            if surge_info["surge"]:
                # 시가총액 필터
                try:
                    info = yf.Ticker(ticker).info
                    market_cap_b = info.get("marketCap", 0) / 1e9
                    if market_cap_b < self.min_market_cap_b:
                        continue
                except Exception:
                    market_cap_b = None

                results.append({
                    "ticker": ticker,
                    "market_cap_b": round(market_cap_b, 1) if market_cap_b else None,
                    **surge_info,
                })

        # 비율 높은 순으로 정렬
        results.sort(key=lambda x: x["ratio_5d"], reverse=True)
        return results


if __name__ == "__main__":
    config = {
        "avg_period_days": 252,
        "surge_multiplier": 3.0,
        "min_market_cap_b": 5,
    }

    analyzer = VolumeAnalyzer(config)

    # 단일 종목 테스트
    df = analyzer.fetch_data("NVDA")
    if df is not None:
        result = analyzer.detect_surge(df)
        print(f"NVDA 거래대금 폭증 분석: {result}")

    # 샘플 종목 스캔
    test_tickers = ["NVDA", "AVGO", "NFLX", "V", "MA", "AAPL", "MSFT", "TSLA"]
    surge_list = analyzer.scan_universe(test_tickers)
    print(f"\n거래대금 폭증 종목 ({len(surge_list)}개):")
    for item in surge_list:
        print(f"  {item['ticker']}: {item['ratio_5d']}배 (5일 평균)")
