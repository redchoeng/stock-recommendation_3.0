"""
Engine 2: 매크로 리스크 점수 산출
- CPI, 실업률, VIX, 장단기 금리차 → 종합 리스크 점수
- risk_score > 0.7 → 방어 모드 트리거
"""


class RiskScorer:
    """매크로 지표 기반 시장 리스크 점수 산출"""

    def __init__(self, config: dict):
        self.weights = config.get("risk_weights", {
            "cpi_change": 0.2,
            "unemployment_change": 0.3,
            "vix_level": 0.3,
            "yield_curve": 0.2,
        })
        self.triggers = config.get("triggers", {
            "vix_above": 25,
            "unemployment_spike_pct": 0.3,
            "sp500_drawdown_pct": -5,
        })

    def calculate_risk(self, macro_data: dict) -> dict:
        """종합 리스크 점수 계산 (0.0 ~ 1.0)"""
        scores = {}

        # 1. CPI 변동 점수 (물가 상승 → 리스크)
        cpi = macro_data.get("fred", {}).get("cpi", {})
        cpi_change = cpi.get("change")
        if cpi_change is not None:
            # CPI 월간 변동 0.3% 이상이면 위험 신호
            scores["cpi"] = min(abs(cpi_change) / 0.5, 1.0)
        else:
            scores["cpi"] = 0.3  # fallback

        # 2. 실업률 변동 점수
        unemp = macro_data.get("fred", {}).get("unemployment", {})
        unemp_change = unemp.get("change")
        if unemp_change is not None:
            # 실업률 상승 → 리스크 (하락은 긍정적)
            scores["unemployment"] = max(0, min(unemp_change / 0.5, 1.0))
        else:
            scores["unemployment"] = 0.3

        # 3. VIX 레벨 점수
        vix = macro_data.get("vix", {})
        vix_current = vix.get("current")
        if vix_current is not None:
            # VIX 15 이하: 안정, 25 이상: 위험, 35 이상: 극한
            scores["vix"] = min(max((vix_current - 15) / 20, 0), 1.0)
        else:
            scores["vix"] = 0.3

        # 4. 장단기 금리차 (yield curve inversion)
        yield_10y = macro_data.get("fred", {}).get("yield_10y", {}).get("current")
        yield_2y = macro_data.get("fred", {}).get("yield_2y", {}).get("current")
        if yield_10y is not None and yield_2y is not None:
            spread = yield_10y - yield_2y
            # 역전 (음수) → 리스크 높음
            if spread < 0:
                scores["yield_curve"] = min(abs(spread) / 1.0, 1.0)
            else:
                scores["yield_curve"] = max(0, 0.3 - spread * 0.1)
        else:
            scores["yield_curve"] = 0.3

        # 가중 평균 리스크 점수
        risk_score = (
            scores.get("cpi", 0) * self.weights["cpi_change"]
            + scores.get("unemployment", 0) * self.weights["unemployment_change"]
            + scores.get("vix", 0) * self.weights["vix_level"]
            + scores.get("yield_curve", 0) * self.weights["yield_curve"]
        )

        # 방어 모드 판단
        defense_mode = False
        defense_reasons = []

        if vix_current and vix_current > self.triggers["vix_above"]:
            defense_mode = True
            defense_reasons.append(f"VIX {vix_current} > {self.triggers['vix_above']}")

        if unemp_change and unemp_change > self.triggers["unemployment_spike_pct"]:
            defense_mode = True
            defense_reasons.append(f"실업률 급등 +{unemp_change}%p")

        sp500 = macro_data.get("sp500", {})
        drawdown = sp500.get("drawdown_pct")
        if drawdown and drawdown < self.triggers["sp500_drawdown_pct"]:
            defense_mode = True
            defense_reasons.append(f"S&P500 {drawdown}% 하락")

        if risk_score > 0.7:
            defense_mode = True
            defense_reasons.append(f"리스크 점수 {risk_score:.2f} > 0.7")

        return {
            "risk_score": round(risk_score, 3),
            "component_scores": scores,
            "defense_mode": defense_mode,
            "defense_reasons": defense_reasons,
            "vix_current": vix_current,
            "sp500_drawdown": drawdown,
        }


if __name__ == "__main__":
    # 테스트: 가상 매크로 데이터
    mock_macro = {
        "vix": {"current": 22.5, "ma_20": 20.0},
        "sp500": {"current": 5800, "high_52w": 6100, "drawdown_pct": -4.9},
        "fred": {
            "cpi": {"current": 315.2, "previous": 314.8, "change": 0.4},
            "unemployment": {"current": 4.1, "previous": 4.0, "change": 0.1},
            "yield_10y": {"current": 4.25, "previous": 4.20, "change": 0.05},
            "yield_2y": {"current": 4.15, "previous": 4.10, "change": 0.05},
        },
    }

    config = {
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
    }

    scorer = RiskScorer(config)
    result = scorer.calculate_risk(mock_macro)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
