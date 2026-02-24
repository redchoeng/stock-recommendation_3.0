"""
DB 연동 모듈
- SQLite (개발) / PostgreSQL (운영) 지원
- 스캔 결과, 매크로, NLP, 리포트 저장 & 조회
"""
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, ScanResult, MacroSnapshot, NLPAnalysis, FinalReport, Watchlist


class Database:
    """DB 연동 통합 인터페이스"""

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        storage = config.get("storage", {})
        db_type = storage.get("db_type", "sqlite")

        if db_type == "sqlite":
            db_path = storage.get("sqlite_path", "data/stock_engine.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        else:
            import os
            db_url = os.environ.get("DATABASE_URL", storage.get("postgresql_url", ""))
            self.engine = create_engine(db_url, echo=False)

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    # -------------------------------------------------------
    # Engine 1: 스캔 결과
    # -------------------------------------------------------

    def save_scan_results(self, results: list[dict], scan_type: str):
        """퀀트 스캔 결과 저장"""
        with self.get_session() as session:
            for r in results:
                record = ScanResult(
                    ticker=r["ticker"],
                    scan_type=scan_type,
                    market_cap_b=r.get("market_cap_b"),
                    ratio_1d=r.get("ratio_1d"),
                    ratio_5d=r.get("ratio_5d"),
                    details=r,
                )
                session.add(record)
            session.commit()

    def get_recent_scans(self, scan_type: str, days: int = 7) -> list[dict]:
        """최근 N일 스캔 결과 조회"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            rows = (
                session.query(ScanResult)
                .filter(ScanResult.scan_type == scan_type)
                .filter(ScanResult.scan_date >= cutoff)
                .order_by(desc(ScanResult.scan_date))
                .all()
            )
            return [r.details for r in rows]

    # -------------------------------------------------------
    # Engine 2: 매크로 스냅샷
    # -------------------------------------------------------

    def save_macro_snapshot(self, risk_result: dict):
        """매크로 리스크 스냅샷 저장"""
        with self.get_session() as session:
            record = MacroSnapshot(
                risk_score=risk_result["risk_score"],
                defense_mode=risk_result["defense_mode"],
                vix_current=risk_result.get("vix_current"),
                sp500_drawdown=risk_result.get("sp500_drawdown"),
                component_scores=risk_result.get("component_scores"),
                defense_reasons=risk_result.get("defense_reasons"),
            )
            session.add(record)
            session.commit()

    def get_macro_history(self, days: int = 30) -> list[dict]:
        """매크로 히스토리 조회"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            rows = (
                session.query(MacroSnapshot)
                .filter(MacroSnapshot.snapshot_date >= cutoff)
                .order_by(desc(MacroSnapshot.snapshot_date))
                .all()
            )
            return [
                {
                    "date": r.snapshot_date.isoformat(),
                    "risk_score": r.risk_score,
                    "defense_mode": r.defense_mode,
                    "vix": r.vix_current,
                }
                for r in rows
            ]

    # -------------------------------------------------------
    # Engine 3: NLP 분석
    # -------------------------------------------------------

    def save_nlp_analysis(self, results: list[dict]):
        """NLP 분석 결과 저장"""
        with self.get_session() as session:
            for r in results:
                record = NLPAnalysis(
                    ticker=r.get("ticker"),
                    buzz_score=r.get("buzz_score"),
                    substance_score=r.get("earnings_substance_score", r.get("substance_score")),
                    total_score=r.get("total_score"),
                    verdict=r.get("verdict"),
                    capex_growing=r.get("capex_growing"),
                    hardware_revenue_pct=r.get("hardware_revenue_pct"),
                    earnings_summary=r.get("earnings_summary"),
                    filing_summary=r.get("filing_summary"),
                    details=r,
                )
                session.add(record)
            session.commit()

    # -------------------------------------------------------
    # 최종 리포트
    # -------------------------------------------------------

    def save_final_report(self, picks: list[dict]):
        """최종 리포트 저장"""
        with self.get_session() as session:
            for p in picks:
                record = FinalReport(
                    ticker=p["ticker"],
                    quant_score=p["quant_score"],
                    macro_score=p["macro_score"],
                    nlp_score=p["nlp_score"],
                    total_score=p["total_score"],
                    signal=p["signal"],
                )
                session.add(record)
            session.commit()

    def get_latest_report(self) -> list[dict]:
        """최신 리포트 조회"""
        with self.get_session() as session:
            # 가장 최근 날짜의 리포트
            latest = session.query(FinalReport).order_by(desc(FinalReport.report_date)).first()
            if not latest:
                return []

            rows = (
                session.query(FinalReport)
                .filter(FinalReport.report_date >= latest.report_date.replace(hour=0, minute=0, second=0))
                .order_by(desc(FinalReport.total_score))
                .all()
            )
            return [
                {
                    "ticker": r.ticker,
                    "quant_score": r.quant_score,
                    "macro_score": r.macro_score,
                    "nlp_score": r.nlp_score,
                    "total_score": r.total_score,
                    "signal": r.signal,
                    "date": r.report_date.isoformat(),
                }
                for r in rows
            ]

    # -------------------------------------------------------
    # 감시 종목
    # -------------------------------------------------------

    def add_to_watchlist(self, ticker: str, name: str = "", reason: str = ""):
        """감시 종목 추가"""
        with self.get_session() as session:
            existing = session.query(Watchlist).filter_by(ticker=ticker.upper()).first()
            if existing:
                existing.active = True
                existing.reason = reason or existing.reason
            else:
                session.add(Watchlist(
                    ticker=ticker.upper(),
                    name=name,
                    reason=reason,
                ))
            session.commit()

    def get_watchlist(self) -> list[dict]:
        """활성 감시 종목 조회"""
        with self.get_session() as session:
            rows = session.query(Watchlist).filter_by(active=True).all()
            return [
                {"ticker": r.ticker, "name": r.name, "reason": r.reason}
                for r in rows
            ]
