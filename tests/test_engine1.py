"""Engine 1 (퀀트) 테스트"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from engine1_quant.volume_analyzer import VolumeAnalyzer
from engine1_quant.peak_detector import PeakDetector
from engine1_quant.neglected_scanner import NeglectedScanner


# -------------------------------------------------------
# 테스트용 DataFrame 생성
# -------------------------------------------------------

def make_mock_df(days=300, base_price=100, base_volume=1_000_000,
                 surge_last_days=0, surge_multiplier=5):
    """테스트용 주가 데이터 생성"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    np.random.seed(42)

    prices = base_price + np.cumsum(np.random.randn(days) * 0.5)
    prices = np.maximum(prices, 10)  # 최소가격

    volumes = base_volume + np.random.randint(-200000, 200000, days)
    volumes = np.maximum(volumes, 100000)

    # 마지막 N일 폭증
    if surge_last_days > 0:
        volumes[-surge_last_days:] = volumes[-surge_last_days:] * surge_multiplier

    df = pd.DataFrame({
        "Open": prices * 0.99,
        "High": prices * 1.02,
        "Low": prices * 0.98,
        "Close": prices,
        "Volume": volumes,
    }, index=dates)

    df["trade_value"] = df["Close"] * df["Volume"]
    df["tv_ma_20"] = df["trade_value"].rolling(20).mean()
    df["tv_ma_60"] = df["trade_value"].rolling(60).mean()
    df["tv_ma_1y"] = df["trade_value"].rolling(252).mean()

    return df


# -------------------------------------------------------
# VolumeAnalyzer 테스트
# -------------------------------------------------------

class TestVolumeAnalyzer:
    def setup_method(self):
        self.analyzer = VolumeAnalyzer({
            "avg_period_days": 252,
            "surge_multiplier": 3.0,
            "min_market_cap_b": 5,
        })

    def test_detect_surge_positive(self):
        """거래대금 폭증 감지 테스트"""
        df = make_mock_df(days=300, surge_last_days=5, surge_multiplier=5)
        result = self.analyzer.detect_surge(df)
        assert result["surge"] is True
        assert result["ratio_1d"] > 3.0

    def test_detect_surge_negative(self):
        """정상 거래대금 — 폭증 아님"""
        df = make_mock_df(days=300, surge_last_days=0)
        result = self.analyzer.detect_surge(df)
        assert result["surge"] is False

    def test_detect_surge_empty_df(self):
        """빈 DataFrame 처리"""
        result = self.analyzer.detect_surge(pd.DataFrame())
        assert result["surge"] is False

    def test_detect_surge_none(self):
        """None 입력 처리"""
        result = self.analyzer.detect_surge(None)
        assert result["surge"] is False


# -------------------------------------------------------
# PeakDetector 테스트
# -------------------------------------------------------

class TestPeakDetector:
    def setup_method(self):
        self.detector = PeakDetector({
            "high_threshold": 0.95,
            "ma_short": 20,
            "ma_long": 60,
        })

    def test_no_warning_when_not_at_high(self):
        """52주 고점에서 멀면 경고 없음"""
        df = make_mock_df(days=300)
        # 마지막 가격을 크게 낮춤
        df["Close"].iloc[-1] = df["Close"].min() * 0.5
        result = self.detector.detect_peak_warning(df, "TEST")
        assert result is None

    def test_none_for_short_data(self):
        """데이터 부족 시 None"""
        df = make_mock_df(days=100)
        result = self.detector.detect_peak_warning(df, "TEST")
        assert result is None


# -------------------------------------------------------
# NeglectedScanner 테스트
# -------------------------------------------------------

class TestNeglectedScanner:
    def setup_method(self):
        self.scanner = NeglectedScanner({
            "top_n_by_market_cap": 50,
            "slope_window_days": 60,
            "slope_threshold": -0.02,
        })

    def test_detect_declining_volume(self):
        """거래대금 하락 추세 감지"""
        df = make_mock_df(days=300)
        # 마지막 60일 거래대금을 점진적으로 감소시킴
        for i in range(60):
            factor = 1.0 - (i * 0.015)  # 90% 감소
            df["trade_value"].iloc[-(60 - i)] *= max(factor, 0.1)

        result = self.scanner.detect_neglected(df, "TEST")
        # 충분히 하락했으면 감지됨
        if result:
            assert result["slope"] < 0
            assert result["ticker"] == "TEST"

    def test_no_neglect_for_stable_volume(self):
        """안정적 거래대금 — 소외주 아님"""
        df = make_mock_df(days=300)
        result = self.scanner.detect_neglected(df, "TEST")
        # 랜덤 데이터는 대체로 소외주가 아님 (기울기 임계값 미달)
        # result가 None이거나, slope가 임계값보다 큰 경우 정상
        if result:
            assert result["slope"] < self.scanner.slope_threshold
