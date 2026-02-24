"""
유니버스 티커 자동 로드
- S&P 500, NASDAQ 100 등 주요 인덱스 구성종목 가져오기
- Wikipedia에서 실시간 크롤링 + 로컬 캐시
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


CACHE_DIR = Path("data/cache")
CACHE_EXPIRY_HOURS = 24


def _load_cache(name: str) -> Optional[list[str]]:
    """로컬 캐시에서 티커 목록 로드"""
    cache_file = CACHE_DIR / f"{name}_tickers.json"
    if not cache_file.exists():
        return None

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
    if datetime.now() - cached_at > timedelta(hours=CACHE_EXPIRY_HOURS):
        return None  # 캐시 만료

    return data.get("tickers", [])


def _save_cache(name: str, tickers: list[str]):
    """캐시 저장"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{name}_tickers.json"
    cache_file.write_text(
        json.dumps({"cached_at": datetime.now().isoformat(), "tickers": tickers},
                    ensure_ascii=False),
        encoding="utf-8",
    )


def get_sp500_tickers() -> list[str]:
    """S&P 500 구성종목 티커 가져오기 (Wikipedia)"""
    cached = _load_cache("sp500")
    if cached:
        return cached

    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        tickers = sorted(df["Symbol"].str.replace(".", "-", regex=False).tolist())

        _save_cache("sp500", tickers)
        print(f"[Universe] S&P 500: {len(tickers)} tickers loaded")
        return tickers

    except Exception as e:
        print(f"[Universe ERROR] S&P 500 fetch failed: {e}")
        return _get_fallback_sp500()


def get_nasdaq100_tickers() -> list[str]:
    """NASDAQ 100 구성종목 티커 가져오기 (Wikipedia)"""
    cached = _load_cache("nasdaq100")
    if cached:
        return cached

    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        tables = pd.read_html(url)
        # NASDAQ 100 테이블 찾기
        for table in tables:
            if "Ticker" in table.columns:
                tickers = sorted(table["Ticker"].str.replace(".", "-", regex=False).tolist())
                _save_cache("nasdaq100", tickers)
                print(f"[Universe] NASDAQ 100: {len(tickers)} tickers loaded")
                return tickers

        raise ValueError("Ticker column not found")

    except Exception as e:
        print(f"[Universe ERROR] NASDAQ 100 fetch failed: {e}")
        return _get_fallback_nasdaq100()


def get_universe(name: str) -> list[str]:
    """설정에 따른 유니버스 로드"""
    if name == "sp500":
        return get_sp500_tickers()
    elif name == "nasdaq100":
        return get_nasdaq100_tickers()
    elif name == "all_us":
        sp500 = set(get_sp500_tickers())
        nasdaq = set(get_nasdaq100_tickers())
        return sorted(sp500 | nasdaq)
    else:
        print(f"[Universe] Unknown universe '{name}', using S&P 500")
        return get_sp500_tickers()


def _get_fallback_sp500() -> list[str]:
    """S&P 500 하드코딩 폴백 (상위 100개)"""
    return [
        "AAPL", "ABBV", "ABT", "ACN", "ADBE", "ADM", "ADP", "ADSK", "AEP", "AFL",
        "AIG", "AMAT", "AMD", "AMGN", "AMZN", "AVGO", "AXP", "BA", "BAC", "BDX",
        "BIIB", "BK", "BKNG", "BLK", "BMY", "BRK-B", "BSX", "C", "CAT", "CB",
        "CCI", "CDNS", "CI", "CL", "CMCSA", "CME", "COP", "COST", "CRM", "CSCO",
        "CVS", "CVX", "D", "DE", "DHR", "DIS", "DUK", "ECL", "EL", "EMR",
        "EOG", "EW", "EXC", "F", "FDX", "FISV", "GD", "GE", "GILD", "GM",
        "GOOGL", "GPN", "GS", "HD", "HON", "IBM", "ICE", "INTC", "INTU", "ISRG",
        "JNJ", "JPM", "KHC", "KO", "LIN", "LLY", "LMT", "LOW", "MA", "MCD",
        "MDLZ", "MDT", "MET", "META", "MMM", "MO", "MRK", "MS", "MSFT", "NEE",
        "NFLX", "NKE", "NOC", "NVDA", "ORCL", "PEP", "PFE", "PG", "PLTR", "PM",
    ]


def _get_fallback_nasdaq100() -> list[str]:
    """NASDAQ 100 하드코딩 폴백 (주요 종목)"""
    return [
        "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
        "AMZN", "ANSS", "ASML", "AVGO", "AZN", "BIIB", "BKNG", "BKR", "CDNS", "CEG",
        "CHTR", "CMCSA", "COST", "CPRT", "CRM", "CRWD", "CSCO", "CSGP", "CTAS", "CTSH",
        "DDOG", "DLTR", "DXCM", "EA", "ENPH", "EXC", "FANG", "FAST", "FTNT", "GILD",
        "GOOGL", "GFS", "HON", "IDXX", "ILMN", "INTC", "INTU", "ISRG", "JD", "KDP",
        "KHC", "KLAC", "LRCX", "LULU", "MAR", "MCHP", "MDB", "MDLZ", "MELI", "META",
        "MNST", "MRNA", "MRVL", "MSFT", "MU", "NFLX", "NVDA", "NXPI", "ODFL", "ON",
        "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR", "PYPL", "QCOM", "REGN",
        "ROST", "SBUX", "SIRI", "SNPS", "TEAM", "TMUS", "TSLA", "TTD", "TXN", "VRSK",
        "VRTX", "WBA", "WBD", "WDAY", "XEL", "ZS",
    ]


if __name__ == "__main__":
    sp500 = get_sp500_tickers()
    print(f"S&P 500: {len(sp500)} tickers")
    print(f"  First 10: {sp500[:10]}")

    nasdaq = get_nasdaq100_tickers()
    print(f"NASDAQ 100: {len(nasdaq)} tickers")
    print(f"  First 10: {nasdaq[:10]}")
