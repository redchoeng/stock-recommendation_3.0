"""
Engine 3: SEC Edgar 스크래퍼
- 10-K/10-Q 보고서 텍스트 수집
- SEC EDGAR FULL-TEXT SEARCH API 활용
"""
import re
import time
from typing import Optional
import requests
from bs4 import BeautifulSoup


class SECScraper:
    """SEC Edgar에서 기업 공시 텍스트 수집"""

    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"

    def __init__(self, config: dict):
        self.user_agent = config.get("user_agent", "StockEngine admin@example.com")
        self.filing_types = config.get("filing_types", ["10-K", "10-Q"])
        self.max_filings = config.get("max_filings_per_ticker", 4)
        self.headers = {"User-Agent": self.user_agent}
        self._cik_cache = {}

    def get_cik(self, ticker: str) -> Optional[str]:
        """티커 → CIK 번호 변환"""
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        try:
            resp = requests.get(self.COMPANY_TICKERS_URL, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    self._cik_cache[ticker] = cik
                    return cik

            print(f"[SEC] CIK not found for {ticker}")
            return None

        except Exception as e:
            print(f"[SEC ERROR] CIK lookup failed for {ticker}: {e}")
            return None

    def get_filing_urls(self, ticker: str, filing_type: str = "10-K") -> list[dict]:
        """최근 공시 URL 목록 조회"""
        cik = self.get_cik(ticker)
        if not cik:
            return []

        try:
            url = self.SUBMISSIONS_URL.format(cik=cik)
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])
            dates = recent.get("filingDate", [])

            filings = []
            for i, form in enumerate(forms):
                if form == filing_type and len(filings) < self.max_filings:
                    accession = accessions[i].replace("-", "")
                    filings.append({
                        "type": form,
                        "date": dates[i],
                        "accession": accession,
                        "accession_raw": accessions[i],
                        "primary_doc": primary_docs[i],
                        "url": self.FILING_URL.format(
                            cik=cik.lstrip("0"),
                            accession=accession,
                            filename=primary_docs[i],
                        ),
                    })

            return filings

        except Exception as e:
            print(f"[SEC ERROR] Filing lookup failed for {ticker}: {e}")
            return []

    def fetch_filing_text(self, url: str, max_chars: int = 50000) -> Optional[str]:
        """공시 문서에서 텍스트 추출"""
        try:
            time.sleep(0.2)  # SEC rate limit 준수
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "lxml")

            # 스크립트/스타일 제거
            for tag in soup(["script", "style"]):
                tag.decompose()

            text = soup.get_text(separator="\n")

            # 연속 공백/줄바꿈 정리
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            text = text.strip()

            if len(text) > max_chars:
                text = text[:max_chars]

            return text

        except Exception as e:
            print(f"[SEC ERROR] Failed to fetch filing: {e}")
            return None

    def get_latest_filing(self, ticker: str, filing_type: str = "10-K") -> Optional[dict]:
        """최신 공시 텍스트 가져오기 (통합 메서드)"""
        filings = self.get_filing_urls(ticker, filing_type)

        if not filings:
            # 10-K 없으면 10-Q로 폴백
            if filing_type == "10-K":
                filings = self.get_filing_urls(ticker, "10-Q")
            if not filings:
                return None

        latest = filings[0]
        text = self.fetch_filing_text(latest["url"])

        if not text:
            return None

        return {
            "ticker": ticker,
            "type": latest["type"],
            "date": latest["date"],
            "url": latest["url"],
            "text": text,
        }


if __name__ == "__main__":
    config = {
        "user_agent": "StockEngine admin@example.com",
        "filing_types": ["10-K", "10-Q"],
        "max_filings_per_ticker": 4,
    }

    scraper = SECScraper(config)

    # CIK 조회 테스트
    cik = scraper.get_cik("TER")
    print(f"Teradyne CIK: {cik}")

    # 최신 10-K 가져오기
    filing = scraper.get_latest_filing("TER")
    if filing:
        print(f"\nFiling: {filing['type']} ({filing['date']})")
        print(f"URL: {filing['url']}")
        print(f"Text length: {len(filing['text'])} chars")
        print(f"Preview: {filing['text'][:500]}...")
    else:
        print("Filing not found")
