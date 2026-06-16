#!/bin/bash
# ASR sistemi - tüm servisleri başlatır.
# Bunu kendi terminalinde çalıştır: ./start_servers.sh

cd "$(dirname "$0")"
ROOT="$(pwd)"

# Portlar
WHISPER_PORT=8003
PROXY_PORT=8002
WEB_PORT=8080

# Whisper modeli: ggml-small.bin sende bozuk (not all tensors loaded).
# Önce tam base model, yoksa test modeli kullan (sunucu kesin başlasın).
if [ -f "$ROOT/native_asr/models/ggml-base.bin" ]; then
  WHISPER_MODEL="$ROOT/native_asr/models/ggml-base.bin"
elif [ -f "$ROOT/native_asr/models/for-tests-ggml-base.bin" ]; then
  WHISPER_MODEL="$ROOT/native_asr/models/for-tests-ggml-base.bin"
else
  WHISPER_MODEL="$ROOT/native_asr/models/ggml-small.bin"
fi

echo "=== ASR Servisleri Başlatılıyor ==="
echo "  Bu scripti Cursor dışında çalıştır: Terminal.app veya iTerm."
echo "  Whisper:  http://127.0.0.1:$WHISPER_PORT (model: $(basename $WHISPER_MODEL))"
echo "  Proxy:    http://127.0.0.1:$PROXY_PORT"
echo "  Web:      http://127.0.0.1:$WEB_PORT"
echo ""

# Eski işlemleri durdur (bu portlarda çalışan)
for port in $WHISPER_PORT $PROXY_PORT $WEB_PORT; do
  pid=$(lsof -ti:$port 2>/dev/null)
  if [ -n "$pid" ]; then
    echo "Port $port dolu (PID $pid), durduruluyor..."
    kill $pid 2>/dev/null
  fi
done
echo "Portlar temizleniyor (2 sn)..."
sleep 2

# 1) Whisper server (önce portu boşalt, sonra başlat)
echo "[1/3] Whisper server başlatılıyor (model: $(basename $WHISPER_MODEL))..."
cd "$ROOT/native_asr"
./build/bin/whisper-server --host 127.0.0.1 --port $WHISPER_PORT -m "$WHISPER_MODEL" -l tr -ng &
WHISPER_PID=$!
cd "$ROOT"
# Port 8003 açılana kadar bekle (en fazla 15 sn)
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  sleep 1
  if lsof -ti:$WHISPER_PORT >/dev/null 2>&1; then
    echo "  OK (PID $WHISPER_PID, port $WHISPER_PORT açık)"
    break
  fi
  if ! kill -0 $WHISPER_PID 2>/dev/null; then
    echo "  HATA: Whisper çöktü. Model bozuk olabilir."
    echo "  Çözüm: cd native_asr/models && bash download-ggml-model.sh base"
    break
  fi
done
if ! lsof -ti:$WHISPER_PORT >/dev/null 2>&1; then
  echo "  UYARI: Whisper port $WHISPER_PORT açmadı. Offline mod çalışmaz."
fi
if [ "$(basename $WHISPER_MODEL)" = "for-tests-ggml-base.bin" ]; then
  echo ""
  echo "  ⚠️  TEST MODELİ: Bu model transkripsiyon YAPMAZ (ekranda metin çıkmaz)."
  echo "      Gerçek model indirmek için: cd $ROOT/native_asr/models && bash download-ggml-model.sh base"
  echo ""
fi

# 2) Streaming proxy
echo "[2/3] Streaming proxy başlatılıyor..."
python3 native_streaming_server.py &
PROXY_PID=$!
sleep 1
if kill -0 $PROXY_PID 2>/dev/null; then
  echo "  OK (PID $PROXY_PID)"
else
  echo "  HATA: Proxy başlamadı."
fi

# 3) Web sunucusu (8080 doluysa 8888 dene)
echo "[3/3] Web sunucusu başlatılıyor..."
python3 -m http.server $WEB_PORT &
WEB_PID=$!
sleep 2
if lsof -ti:$WEB_PORT >/dev/null 2>&1; then
  echo "  OK (PID $WEB_PID, http://localhost:$WEB_PORT)"
else
  WEB_PORT=8888
  echo "  Port 8080 dolu, $WEB_PORT deniyor..."
  python3 -m http.server $WEB_PORT &
  WEB_PID=$!
  sleep 1
  if lsof -ti:$WEB_PORT >/dev/null 2>&1; then
    echo "  OK (PID $WEB_PID, http://localhost:$WEB_PORT)"
  else
    echo "  HATA: Web sunucusu başlamadı (8080 ve 8888 dolu olabilir)."
  fi
fi

echo ""
echo "=== Hazır ==="
echo "  Tarayıcıda aç: http://localhost:$WEB_PORT"
echo "  Durdurmak için: kill $WHISPER_PID $PROXY_PID $WEB_PID"
echo "  veya Ctrl+C"
echo ""

# Tarayıcıyı aç (macOS)
if command -v open >/dev/null 2>&1; then
  sleep 2
  open "http://localhost:$WEB_PORT"
fi

# Ön planda bekle (Ctrl+C ile hepsini durdur)
wait
