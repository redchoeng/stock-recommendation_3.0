#!/bin/bash
# Ollama 설치 및 모델 다운로드 스크립트

set -e

echo "=== Ollama Setup ==="

# 1. Ollama 설치 확인
if command -v ollama &> /dev/null; then
    echo "[OK] Ollama already installed: $(ollama --version)"
else
    echo "[INFO] Installing Ollama..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Please install Ollama from https://ollama.com/download"
        exit 1
    elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
        echo "Please install Ollama from https://ollama.com/download"
        exit 1
    fi
fi

# 2. Ollama 서비스 시작
echo "[INFO] Starting Ollama service..."
ollama serve &
sleep 3

# 3. 모델 다운로드
echo "[INFO] Downloading models..."

# 기본 모델 (8GB VRAM)
echo "  Downloading llama3.1:8b..."
ollama pull llama3.1:8b

# 선택적 모델
read -p "Download deepseek-r1:8b (reasoning model)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ollama pull deepseek-r1:8b
fi

read -p "Download mistral:7b (fast & light)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ollama pull mistral:7b
fi

# 4. 확인
echo ""
echo "=== Installed Models ==="
ollama list

echo ""
echo "[DONE] Ollama setup complete!"
echo "  Test: ollama run llama3.1:8b 'Hello'"
