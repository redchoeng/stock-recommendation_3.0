#!/bin/bash
# DB 초기화 스크립트

set -e

echo "=== Database Initialization ==="

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 1. data 디렉토리 생성
mkdir -p data/reports

# 2. Python으로 SQLAlchemy 테이블 생성
echo "[INFO] Creating database tables..."
python -c "
from storage.db import Database
db = Database()
print('[OK] Database initialized successfully')
print(f'  Location: {db.engine.url}')
"

# 3. 초기 감시 종목 로드 (watchlist.yaml → DB)
echo "[INFO] Loading initial watchlist..."
python -c "
import yaml
from storage.db import Database

db = Database()
with open('config/watchlist.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

for item in config.get('watchlist', []):
    db.add_to_watchlist(item['ticker'], item.get('name', ''), item.get('reason', ''))
    print(f'  Added: {item[\"ticker\"]}')

print('[OK] Watchlist loaded')
"

echo ""
echo "[DONE] Database initialization complete!"
