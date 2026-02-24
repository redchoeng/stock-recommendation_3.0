"""
Engine 2: 방어주 스위칭 룰 엔진
- 리스크 점수 기반 방어 포트폴리오 비중 조절
- 섹터별 방어주 추천
"""
from typing import Optional
import pandas as pd
import yfinance as yf


class HedgeAllocator:
    """매크로 리스크 기반 방어 포트폴리오 배분"""

    def __init__(self, config: dict):
        self.defense_tickers = config.get("defense_tickers", {})
        self.rebalance_ratio = config.get("defense_rebalance_ratio", 0.3)

    def get_defense_allocation(self, risk_result: dict) -> dict:
        """리스크 결과 기반 방어 배분 산출"""
        if not risk_result.get("defense_mode"):
            return {
                "defense_mode": False,
                "defense_ratio": 0,
                "message": "시장 안정 — 방어 배분 불필요",
                "sectors": {},
            }

        risk_score = risk_result.get("risk_score", 0.5)

        # 리스크 점수에 비례하여 방어 비중 조절 (30~50%)
        defense_ratio = min(self.rebalance_ratio + (risk_score - 0.7) * 0.5, 0.5)
        defense_ratio = max(defense_ratio, self.rebalance_ratio)

        # 섹터별 배분 (VIX/금리 상황에 따라 가중)
        vix = risk_result.get("vix_current", 20)
        drawdown = risk_result.get("sp500_drawdown", 0) or 0

        sector_weights = self._calculate_sector_weights(vix, drawdown)

        # 섹터별 추천 종목 + 모멘텀 점수
        sectors = {}
        for sector, weight in sector_weights.items():
            tickers = self.defense_tickers.get(sector, [])
            scored = self._score_defense_tickers(tickers)
            sectors[sector] = {
                "weight": round(weight, 3),
                "tickers": scored,
            }

        return {
            "defense_mode": True,
            "defense_ratio": round(defense_ratio, 3),
            "risk_score": risk_score,
            "reasons": risk_result.get("defense_reasons", []),
            "sectors": sectors,
        }

    def _calculate_sector_weights(self, vix: float, drawdown: float) -> dict:
        """VIX/낙폭 기반 섹터 가중치 결정"""
        weights = {
            "consumer_staples": 0.30,  # 기본 배분
            "utilities": 0.25,
            "gold": 0.25,
            "agricultural": 0.20,
        }

        # VIX 30 이상: 금 비중 확대
        if vix and vix > 30:
            weights["gold"] += 0.10
            weights["agricultural"] -= 0.05
            weights["utilities"] -= 0.05

        # 큰 낙폭: 필수소비재 확대
        if drawdown and drawdown < -10:
            weights["consumer_staples"] += 0.10
            weights["gold"] -= 0.05
            weights["agricultural"] -= 0.05

        # 정규화
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}

    def _score_defense_tickers(self, tickers: list[str]) -> list[dict]:
        """방어주 개별 모멘텀 점수"""
        results = []

        for ticker in tickers:
            try:
                df = yf.download(ticker, period="3mo", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if df.empty or len(df) < 20:
                    results.append({"ticker": ticker, "momentum": None})
                    continue

                # 3개월 수익률
                returns_3m = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

                # 20일 변동성 (안정적일수록 좋음)
                daily_returns = df["Close"].pct_change().dropna()
                volatility = daily_returns.tail(20).std() * 100

                results.append({
                    "ticker": ticker,
                    "returns_3m": round(float(returns_3m), 2),
                    "volatility_20d": round(float(volatility), 3),
                    "momentum": round(float(returns_3m / max(volatility, 0.1)), 2),
                })
            except Exception:
                results.append({"ticker": ticker, "momentum": None})

        # 모멘텀 높은 순 정렬
        results.sort(key=lambda x: x.get("momentum") or -999, reverse=True)
        return results


if __name__ == "__main__":
    config = {
        "defense_tickers": {
            "agricultural": ["ADM", "BG", "CTVA", "DE"],
            "utilities": ["NEE", "DUK", "SO", "AEP"],
            "consumer_staples": ["PG", "KO", "PEP", "CL"],
            "gold": ["GLD", "NEM", "GOLD"],
        },
        "defense_rebalance_ratio": 0.3,
    }

    allocator = HedgeAllocator(config)

    # 방어 모드 시뮬레이션
    mock_risk = {
        "risk_score": 0.75,
        "defense_mode": True,
        "defense_reasons": ["VIX 28 > 25", "리스크 점수 0.75 > 0.7"],
        "vix_current": 28,
        "sp500_drawdown": -6.2,
    }

    allocation = allocator.get_defense_allocation(mock_risk)

    import json
    print(json.dumps(allocation, indent=2, ensure_ascii=False))
