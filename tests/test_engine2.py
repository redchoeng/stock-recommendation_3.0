"""Engine 2 (매크로) 테스트"""
import pytest

from engine2_macro.risk_scorer import RiskScorer
from engine2_macro.hedge_allocator import HedgeAllocator


# -------------------------------------------------------
# RiskScorer 테스트
# -------------------------------------------------------

class TestRiskScorer:
    def setup_method(self):
        self.scorer = RiskScorer({
            "risk_weights": {
                "cpi_change": 0.2,
                "unemployment_change": 0.3,
                "vix_level": 0.3,
                "yield_curve": 0.2,
            },
            "triggers": {
                "vix_above": 25,
                "unemployment_spike_pct": 0.3,
                "sp500_drawdown_pct": -5,
            },
        })

    def test_low_risk_scenario(self):
        """안정적 시장 — 낮은 리스크"""
        macro = {
            "vix": {"current": 14},
            "sp500": {"drawdown_pct": -1.5},
            "fred": {
                "cpi": {"change": 0.1},
                "unemployment": {"change": -0.1},
                "yield_10y": {"current": 4.5},
                "yield_2y": {"current": 4.0},
            },
        }
        result = self.scorer.calculate_risk(macro)
        assert result["risk_score"] < 0.5
        assert result["defense_mode"] is False

    def test_high_risk_vix_spike(self):
        """VIX 급등 — 방어 모드"""
        macro = {
            "vix": {"current": 35},
            "sp500": {"drawdown_pct": -8},
            "fred": {
                "cpi": {"change": 0.5},
                "unemployment": {"change": 0.4},
                "yield_10y": {"current": 3.5},
                "yield_2y": {"current": 4.0},  # 역전
            },
        }
        result = self.scorer.calculate_risk(macro)
        assert result["risk_score"] > 0.5
        assert result["defense_mode"] is True
        assert len(result["defense_reasons"]) > 0

    def test_yield_curve_inversion(self):
        """장단기 금리 역전"""
        macro = {
            "vix": {"current": 20},
            "sp500": {"drawdown_pct": -2},
            "fred": {
                "cpi": {"change": 0.2},
                "unemployment": {"change": 0.0},
                "yield_10y": {"current": 3.8},
                "yield_2y": {"current": 4.5},  # 역전
            },
        }
        result = self.scorer.calculate_risk(macro)
        scores = result["component_scores"]
        assert scores["yield_curve"] > 0.3

    def test_missing_data_fallback(self):
        """데이터 누락 시 fallback"""
        macro = {
            "vix": {"current": None},
            "sp500": {"drawdown_pct": None},
            "fred": {
                "cpi": {"change": None},
                "unemployment": {"change": None},
                "yield_10y": {"current": None},
                "yield_2y": {"current": None},
            },
        }
        result = self.scorer.calculate_risk(macro)
        assert 0 <= result["risk_score"] <= 1
        assert result["defense_mode"] is False  # fallback은 방어 모드 아님


# -------------------------------------------------------
# HedgeAllocator 테스트
# -------------------------------------------------------

class TestHedgeAllocator:
    def setup_method(self):
        self.allocator = HedgeAllocator({
            "defense_tickers": {
                "agricultural": ["ADM", "BG"],
                "utilities": ["NEE", "DUK"],
                "consumer_staples": ["PG", "KO"],
                "gold": ["GLD"],
            },
            "defense_rebalance_ratio": 0.3,
        })

    def test_no_defense_when_safe(self):
        """방어 모드 아닐 때 — 배분 없음"""
        risk_result = {
            "defense_mode": False,
            "risk_score": 0.3,
        }
        result = self.allocator.get_defense_allocation(risk_result)
        assert result["defense_mode"] is False
        assert result["defense_ratio"] == 0

    def test_defense_allocation(self):
        """방어 모드 시 배분 산출"""
        risk_result = {
            "defense_mode": True,
            "risk_score": 0.8,
            "defense_reasons": ["VIX > 25"],
            "vix_current": 30,
            "sp500_drawdown": -7,
        }
        result = self.allocator.get_defense_allocation(risk_result)
        assert result["defense_mode"] is True
        assert result["defense_ratio"] >= 0.3
        assert len(result["sectors"]) > 0

        # 섹터 가중치 합이 1.0
        total_weight = sum(s["weight"] for s in result["sectors"].values())
        assert abs(total_weight - 1.0) < 0.01
