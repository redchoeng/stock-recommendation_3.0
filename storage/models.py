"""
DB 스키마 정의 (SQLAlchemy ORM)
- 스캔 결과, 매크로 스냅샷, NLP 분석, 최종 리포트
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, Text, DateTime, JSON,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ScanResult(Base):
    """Engine 1: 퀀트 스캔 결과"""
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_date = Column(DateTime, default=datetime.utcnow, index=True)
    ticker = Column(String(10), index=True)
    scan_type = Column(String(20))  # surge / peak_warning / neglected
    market_cap_b = Column(Float)
    ratio_1d = Column(Float)
    ratio_5d = Column(Float)
    details = Column(JSON)


class MacroSnapshot(Base):
    """Engine 2: 매크로 스냅샷"""
    __tablename__ = "macro_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(DateTime, default=datetime.utcnow, index=True)
    risk_score = Column(Float)
    defense_mode = Column(Boolean, default=False)
    vix_current = Column(Float)
    sp500_drawdown = Column(Float)
    component_scores = Column(JSON)
    defense_reasons = Column(JSON)


class NLPAnalysis(Base):
    """Engine 3: NLP 분석 결과"""
    __tablename__ = "nlp_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(DateTime, default=datetime.utcnow, index=True)
    ticker = Column(String(10), index=True)
    buzz_score = Column(Float)
    substance_score = Column(Float)
    total_score = Column(Float)
    verdict = Column(String(20))
    capex_growing = Column(Boolean)
    hardware_revenue_pct = Column(Float)
    earnings_summary = Column(Text)
    filing_summary = Column(Text)
    details = Column(JSON)


class FinalReport(Base):
    """통합 최종 리포트"""
    __tablename__ = "final_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(DateTime, default=datetime.utcnow, index=True)
    ticker = Column(String(10), index=True)
    quant_score = Column(Float)
    macro_score = Column(Float)
    nlp_score = Column(Float)
    total_score = Column(Float)
    signal = Column(String(20))  # STRONG_BUY / BUY / HOLD / SELL / AVOID


class Watchlist(Base):
    """감시 종목"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, index=True)
    name = Column(String(100))
    added_date = Column(DateTime, default=datetime.utcnow)
    reason = Column(String(200))
    active = Column(Boolean, default=True)
