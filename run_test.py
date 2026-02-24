"""빠른 테스트: Engine 1 거래대금 스캔"""
from engine1_quant.volume_analyzer import VolumeAnalyzer
from engine1_quant.peak_detector import PeakDetector

# Engine 1-A: 거래대금 폭증
config = {
    "avg_period_days": 252,
    "surge_multiplier": 3.0,
    "min_market_cap_b": 5,
}
analyzer = VolumeAnalyzer(config)

tickers = ["NVDA", "AVGO", "AAPL", "MSFT", "TSLA", "NFLX", "V", "MA", "AMD", "GOOGL", "META", "AMZN", "PLTR"]
print(f"=== Engine 1-A: Volume Surge Scan ({len(tickers)} stocks) ===\n")

for ticker in tickers:
    df = analyzer.fetch_data(ticker)
    if df is not None:
        result = analyzer.detect_surge(df)
        tag = "** SURGE **" if result["surge"] else "           "
        print(f"  {tag} {ticker:6s} | 1d: {result['ratio_1d']:5.2f}x | 5d: {result['ratio_5d']:5.2f}x")

print("\n--- Filtered Surge Stocks (>= 3x, >= $5B) ---")
surge_list = analyzer.scan_universe(tickers)
if surge_list:
    for s in surge_list:
        print(f"  {s['ticker']:6s} | {s['ratio_5d']}x (5d) | MCap ${s.get('market_cap_b', '?')}B")
else:
    print("  (no surge detected)")

# Engine 1-B: 고점 경고
print(f"\n=== Engine 1-B: Peak Warning ===\n")
peak_config = {"high_threshold": 0.95, "ma_short": 20, "ma_long": 60}
detector = PeakDetector(peak_config)
warnings = detector.scan_universe(tickers, analyzer)
if warnings:
    for w in warnings:
        print(f"  {w['warning']:10s} {w['ticker']:6s} | "
              f"Price {w['price_pct_of_high']}% of 52w high | "
              f"TV ratio {w['tv_ratio']}")
else:
    print("  (no peak warnings)")

print("\nDone!")
