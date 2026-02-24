"""Engine 3 (NLP) 테스트 — Ollama 없이 단위 테스트"""
import pytest

from engine3_nlp.llm_analyzer import LLMAnalyzer


class TestLLMAnalyzer:
    def setup_method(self):
        self.analyzer = LLMAnalyzer({
            "model": "llama3.1:8b",
            "temperature": 0.1,
            "max_tokens": 2048,
        })

    def test_parse_json_clean(self):
        """깨끗한 JSON 파싱"""
        text = '{"ticker": "TER", "buzz_score": -2, "substance_score": 7}'
        result = self.analyzer._parse_json(text)
        assert result is not None
        assert result["ticker"] == "TER"
        assert result["buzz_score"] == -2

    def test_parse_json_with_markdown(self):
        """마크다운 코드블록 감싸진 JSON 파싱"""
        text = '```json\n{"ticker": "NVDA", "score": 9}\n```'
        result = self.analyzer._parse_json(text)
        assert result is not None
        assert result["ticker"] == "NVDA"

    def test_parse_json_with_extra_text(self):
        """JSON 앞뒤에 텍스트가 있는 경우"""
        text = 'Here is the result:\n{"ticker": "AMD", "verdict": "BUY"}\nEnd.'
        result = self.analyzer._parse_json(text)
        assert result is not None
        assert result["ticker"] == "AMD"

    def test_parse_json_invalid(self):
        """잘못된 JSON"""
        text = "This is not JSON at all"
        result = self.analyzer._parse_json(text)
        assert result is None

    def test_merge_results_both_present(self):
        """Earnings + Filing 모두 있을 때 병합"""
        earnings = {
            "buzz_score": -3,
            "substance_score": 8,
            "capex_growing": True,
            "hardware_revenue_pct": 45.0,
            "key_positive_keywords": ["capex", "backlog"],
            "key_negative_keywords": ["AI"],
            "summary": "테스트 요약",
        }
        filing = {
            "substance_score": 7,
            "capex_yoy_change_pct": 15,
            "hardware_revenue_pct": 42.0,
            "summary": "Filing 요약",
        }
        result = self.analyzer._merge_results("TER", earnings, filing)

        assert result["ticker"] == "TER"
        assert result["buzz_score"] == -3
        assert result["earnings_substance_score"] == 8
        assert result["filing_substance_score"] == 7
        # 가중 평균: 8*0.6 + 7*0.4 = 7.6, + buzz(-3) = 4.6
        assert 4.0 <= result["total_score"] <= 5.0
        assert result["verdict"] in ("HOLD", "BUY")

    def test_merge_results_earnings_only(self):
        """Earnings만 있을 때"""
        earnings = {
            "buzz_score": -1,
            "substance_score": 9,
            "summary": "Good company",
        }
        result = self.analyzer._merge_results("NVDA", earnings, None)
        assert result["ticker"] == "NVDA"
        assert result["filing_substance_score"] == 0

    def test_merge_results_none(self):
        """둘 다 없을 때"""
        result = self.analyzer._merge_results("FAIL", None, None)
        assert result["ticker"] == "FAIL"
        assert result["total_score"] == 0
        assert result["verdict"] == "AVOID"

    def test_truncate_short(self):
        """짧은 텍스트는 그대로"""
        text = "short text"
        assert self.analyzer._truncate(text, 100) == text

    def test_truncate_long(self):
        """긴 텍스트 자르기"""
        text = "a" * 30000
        result = self.analyzer._truncate(text, 1000)
        assert len(result) < 30000
        assert "[truncated]" in result
