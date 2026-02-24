"""
Engine 3: NLP 실체 검증 엔진 - 로컬 LLM (Ollama) 기반
- Earnings Call 스크립트 & 10-K/10-Q 분석
- 버즈워드 기업 감점, 실체 기업 가산점
"""
import json
import re
from typing import Optional
import ollama


class LLMAnalyzer:
    """로컬 LLM을 활용한 기업 실체 검증"""

    def __init__(self, config: dict):
        self.model = config.get("model", "llama3.1:8b")
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 2048)

    # -------------------------------------------------------
    # 프롬프트 템플릿
    # -------------------------------------------------------

    EARNINGS_ANALYSIS_PROMPT = """You are a senior equity research analyst specializing in US stocks.
Analyze the following Earnings Call transcript and return ONLY a valid JSON object.

## Company: {ticker} ({company_name})
## Quarter: {quarter}

## TRANSCRIPT:
{transcript}

## ANALYSIS CRITERIA:

### Deduction Factors (buzz_score: -10 to 0)
- Repeated use of "AI", "innovation", "disruption", "transformation" WITHOUT specific numbers: -2 each
- Revenue/earnings guidance lowered: -3
- "one-time charge", "restructuring", "impairment" mentioned: -2
- Vague future promises without timelines: -1

### Bonus Factors (substance_score: 0 to 10)
- "Capex increase" / "capital expenditure growth" with specific amounts: +3
- "Test equipment orders" / "backlog growth" with numbers: +3
- "Automation" / "labor cost reduction" / "efficiency gains" with metrics: +2
- Hardware/robotics/semiconductor revenue percentage increasing: +4
- "Recurring revenue" / "subscription" growth with specific %: +2
- Specific customer names / contract amounts mentioned: +1

## OUTPUT (JSON only, no markdown fences):
{{
    "ticker": "{ticker}",
    "quarter": "{quarter}",
    "buzz_score": <-10 to 0>,
    "substance_score": <0 to 10>,
    "capex_growing": <true/false>,
    "capex_detail": "<specific capex info or null>",
    "hardware_revenue_pct": <float or null>,
    "key_positive_keywords": ["keyword1", "keyword2"],
    "key_negative_keywords": ["keyword1", "keyword2"],
    "revenue_guidance": "raised/maintained/lowered/not_mentioned",
    "summary": "<2-3 sentence summary in Korean>",
    "verdict": "STRONG_BUY / BUY / HOLD / AVOID"
}}"""

    FILING_ANALYSIS_PROMPT = """You are a senior equity research analyst.
Analyze the following SEC filing excerpt (10-K or 10-Q) and return ONLY a valid JSON object.

## Company: {ticker}
## Filing Type: {filing_type}

## FILING TEXT:
{filing_text}

## FOCUS AREAS:
1. Revenue breakdown by segment - is hardware/product revenue growing?
2. Capex trends - are they investing in physical assets?
3. R&D spending - is it increasing?
4. Debt levels - any concerns?
5. Key risk factors related to AI/automation adoption

## OUTPUT (JSON only, no markdown fences):
{{
    "ticker": "{ticker}",
    "filing_type": "{filing_type}",
    "revenue_segments": {{"segment_name": "revenue_amount or pct"}},
    "hardware_revenue_pct": <float or null>,
    "capex_total": "<amount>",
    "capex_yoy_change_pct": <float or null>,
    "rd_spending": "<amount>",
    "rd_yoy_change_pct": <float or null>,
    "debt_to_equity": <float or null>,
    "key_findings": ["finding1", "finding2"],
    "risk_flags": ["risk1", "risk2"],
    "substance_score": <0 to 10>,
    "summary": "<2-3 sentence summary in Korean>"
}}"""

    # -------------------------------------------------------
    # 분석 메서드
    # -------------------------------------------------------

    def analyze_earnings(self, ticker: str, company_name: str,
                         quarter: str, transcript: str) -> Optional[dict]:
        """Earnings Call 스크립트 분석"""
        prompt = self.EARNINGS_ANALYSIS_PROMPT.format(
            ticker=ticker,
            company_name=company_name,
            quarter=quarter,
            transcript=self._truncate(transcript, max_chars=12000),
        )
        return self._call_llm(prompt)

    def analyze_filing(self, ticker: str, filing_type: str,
                       filing_text: str) -> Optional[dict]:
        """SEC 10-K/10-Q 분석"""
        prompt = self.FILING_ANALYSIS_PROMPT.format(
            ticker=ticker,
            filing_type=filing_type,
            filing_text=self._truncate(filing_text, max_chars=15000),
        )
        return self._call_llm(prompt)

    def combined_analysis(self, ticker: str, company_name: str,
                          quarter: str, transcript: str,
                          filing_type: str, filing_text: str) -> dict:
        """Earnings + Filing 통합 분석"""
        earnings_result = self.analyze_earnings(ticker, company_name, quarter, transcript)
        filing_result = self.analyze_filing(ticker, filing_type, filing_text)
        return self._merge_results(ticker, earnings_result, filing_result)

    # -------------------------------------------------------
    # 배치 처리
    # -------------------------------------------------------

    def batch_analyze(self, companies: list[dict],
                      earnings_fetcher, sec_fetcher) -> list[dict]:
        """
        여러 기업 일괄 분석
        companies: [{"ticker": "TER", "name": "Teradyne", "quarter": "Q4 2024"}, ...]
        """
        results = []

        for company in companies:
            ticker = company["ticker"]
            print(f"[NLP] Analyzing {ticker}...")

            try:
                transcript = earnings_fetcher.get_transcript(
                    ticker, company.get("quarter", "latest")
                )
                filing = sec_fetcher.get_latest_filing(ticker)

                if transcript:
                    earnings_result = self.analyze_earnings(
                        ticker, company.get("name", ticker),
                        company.get("quarter", ""), transcript
                    )
                else:
                    earnings_result = None
                    print(f"  [WARN] No earnings transcript for {ticker}")

                if filing:
                    filing_result = self.analyze_filing(
                        ticker, filing.get("type", "10-K"),
                        filing.get("text", "")
                    )
                else:
                    filing_result = None
                    print(f"  [WARN] No SEC filing for {ticker}")

                merged = self._merge_results(ticker, earnings_result, filing_result)
                results.append(merged)

            except Exception as e:
                print(f"  [ERROR] {ticker}: {e}")
                results.append({
                    "ticker": ticker,
                    "error": str(e),
                    "total_score": 0,
                    "verdict": "ERROR",
                })

        results.sort(key=lambda x: x.get("total_score", 0), reverse=True)
        return results

    # -------------------------------------------------------
    # 내부 메서드
    # -------------------------------------------------------

    def _call_llm(self, prompt: str) -> Optional[dict]:
        """Ollama 로컬 LLM 호출"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial analyst. Always respond with valid JSON only. No markdown, no explanation."
                    },
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            content = response["message"]["content"].strip()
            return self._parse_json(content)

        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return None

    def _parse_json(self, text: str) -> Optional[dict]:
        """LLM 응답에서 JSON 추출"""
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            print(f"[WARN] JSON 파싱 실패: {text[:200]}...")
            return None

    def _merge_results(self, ticker: str,
                       earnings: Optional[dict],
                       filing: Optional[dict]) -> dict:
        """Earnings + Filing 결과 병합"""
        e = earnings or {}
        f = filing or {}

        buzz_score = e.get("buzz_score", 0)
        earnings_substance = e.get("substance_score", 0)
        filing_substance = f.get("substance_score", 0)

        # 가중 평균 (Earnings 60%, Filing 40%)
        substance_avg = earnings_substance * 0.6 + filing_substance * 0.4

        # 총점: 실체 점수 + 버즈워드 감점 (0~10 스케일)
        total = max(0, min(10, substance_avg + buzz_score))

        if total >= 8:
            verdict = "STRONG_BUY"
        elif total >= 6:
            verdict = "BUY"
        elif total >= 4:
            verdict = "HOLD"
        elif total >= 2:
            verdict = "CAUTION"
        else:
            verdict = "AVOID"

        return {
            "ticker": ticker,
            "buzz_score": buzz_score,
            "earnings_substance_score": earnings_substance,
            "filing_substance_score": filing_substance,
            "total_score": round(total, 2),
            "verdict": verdict,
            "capex_growing": e.get("capex_growing", f.get("capex_yoy_change_pct", 0) or 0 > 0),
            "hardware_revenue_pct": e.get("hardware_revenue_pct") or f.get("hardware_revenue_pct"),
            "key_positive_keywords": e.get("key_positive_keywords", []),
            "key_negative_keywords": e.get("key_negative_keywords", []),
            "earnings_summary": e.get("summary", "N/A"),
            "filing_summary": f.get("summary", "N/A"),
        }

    def _truncate(self, text: str, max_chars: int = 12000) -> str:
        """LLM 컨텍스트 제한 대비 텍스트 자르기"""
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n\n... [truncated] ...\n\n" + text[-half:]


if __name__ == "__main__":
    config = {
        "model": "llama3.1:8b",
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    analyzer = LLMAnalyzer(config)

    sample_transcript = """
    Good afternoon. This is the Q4 2024 earnings call for Teradyne.

    Our automation segment grew 23% year-over-year, driven by strong demand
    for our Universal Robots collaborative robot arms. We shipped over 75,000
    cobots in 2024, a record.

    Capital expenditure increased to $180 million, up 15% from last year,
    primarily for expanding our test equipment manufacturing capacity in Asia.

    Our semiconductor test backlog grew to $1.2 billion, the highest level
    in five years, as customers prepare for next-generation chip testing needs.

    Labor cost reduction initiatives saved $45 million this year through
    automation of our own production lines.

    We are raising our full-year 2025 revenue guidance to $3.2-3.4 billion.
    """

    result = analyzer.analyze_earnings(
        ticker="TER",
        company_name="Teradyne",
        quarter="Q4 2024",
        transcript=sample_transcript,
    )

    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("분석 실패 - Ollama가 실행 중인지 확인하세요: ollama serve")
