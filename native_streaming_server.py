# -*- coding: utf-8 -*-
"""
Offline ASR Streaming Server – Profesyonel ses akışı ve Whisper entegrasyonu

- WebSocket ile 16-bit 16 kHz mono PCM alır
- Belirli süre (CHUNK_DURATION_SEC) dolunca WAV oluşturup Whisper’a gönderir
- Dönen metni partial/final olarak istemciye iletir
- Türkçe tanıma için prompt ve dil ayarları optimize edilmiştir
"""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Python Whisper (fallback): C++ sunucu yoksa veya hep boş dönüyorsa kullanılır
_PYWHISPER_MODEL = None
_EXECUTOR = ThreadPoolExecutor(max_workers=1)

# -----------------------------------------------------------------------------
# Yapılandırma
# -----------------------------------------------------------------------------
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # 16-bit
BYTES_PER_SEC = SAMPLE_RATE * BYTES_PER_SAMPLE

# Whisper’a her seferde gönderilecek süre (saniye). 1.0–1.5 arası doğruluk/gecikme dengesi.
CHUNK_DURATION_SEC = 1.2
CHUNK_BYTES = int(CHUNK_DURATION_SEC * BYTES_PER_SEC)
# Bayt sayısı çift olmalı
if CHUNK_BYTES % 2 != 0:
    CHUNK_BYTES -= 1

WHISPER_URL = "http://127.0.0.1:8003/inference"
WHISPER_TIMEOUT_SEC = 15
SERVER_PORT = 8002

# Türkçe bağlamı: Whisper’ın dil ve kelime dağılımına yardım eder (isim, şehir, günlük kelime)
TURKISH_PROMPT = (
    "Merhaba, nasılsınız? Ben Türkçe konuşuyorum. "
    "İstanbul, Ankara, İzmir. Ahmet, Mehmet, Ayşe, Fatma, Zeynep. "
    "Fatura, ödeme, müşteri hizmetleri, randevu, başvuru, teknik destek. "
    "Evet, hayır, lütfen, teşekkürler, tamam, anladım, bilgi, numara."
)

# Yalnızca bilinen anlamsız / video kalıplarını atla (gerçek konuşmayı silme)
SKIP_PHRASES = frozenset({
    "İzlediğiniz için teşekkürler",
    "İzlediğiniz için teşekkür ederim",
    "Abone olmayı unutmayın",
    "Sears",
    "MBC",
    "Altyazı",
    "Alt yazılar",
})

# -----------------------------------------------------------------------------
# Loglama
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("asr.stream")

# -----------------------------------------------------------------------------
# Yardımcı
# -----------------------------------------------------------------------------


def should_skip(text: str) -> bool:
    """Boş veya yalnızca atlanacak kalıpsa True."""
    t = (text or "").strip()
    if not t:
        return True
    if t in SKIP_PHRASES:
        return True
    return False


def build_wav(pcm_bytes: bytes, rate: int = SAMPLE_RATE) -> bytes:
    """16-bit mono PCM’i WAV dosyasına çevirir."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


def _transcribe_pywhisper(wav_path: str) -> Optional[dict[str, Any]]:
    """Python Whisper ile WAV dosyasını transkribe eder (bloklayan, thread'de çağrılır)."""
    global _PYWHISPER_MODEL
    try:
        import whisper
    except ImportError:
        logger.warning("openai-whisper yüklü değil. Offline tanıma için: pip install openai-whisper")
        return None
    try:
        if _PYWHISPER_MODEL is None:
            logger.info("Python Whisper modeli yükleniyor (ilk seferde ~1 dk sürebilir)...")
            _PYWHISPER_MODEL = whisper.load_model("base", device="cpu", download_root=str(Path.home() / ".cache" / "whisper"))
        r = _PYWHISPER_MODEL.transcribe(wav_path, language="tr", fp16=False, task="transcribe", initial_prompt=TURKISH_PROMPT)
        text = (r.get("text") or "").strip()
        segments = r.get("segments") or []
        return {"text": text, "segments": [{"text": (s.get("text") or "").strip()} for s in segments]}
    except Exception as e:
        logger.exception("Python Whisper hata: %s", e)
        return None


async def call_whisper_native(
    session: aiohttp.ClientSession,
    wav_bytes: bytes,
) -> Optional[dict[str, Any]]:
    """C++ Whisper sunucusuna istek atar. Başarısız veya boşsa None döner."""
    form = aiohttp.FormData()
    form.add_field("file", wav_bytes, filename="audio.wav", content_type="audio/wav")
    form.add_field("language", "tr")
    form.add_field("temperature", "0.0")
    form.add_field("response_format", "verbose_json")
    form.add_field("prompt", TURKISH_PROMPT)
    form.add_field("no_speech_thold", "0.5")
    try:
        timeout = aiohttp.ClientTimeout(total=WHISPER_TIMEOUT_SEC)
        async with session.post(WHISPER_URL, data=form, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None


async def call_whisper(
    session: aiohttp.ClientSession,
    wav_bytes: bytes,
) -> Optional[dict[str, Any]]:
    """
    Önce C++ Whisper'ı dener; yoksa veya cevap boşsa Python Whisper kullanır.
    Böylece gerçek model olmadan da tanıma çalışır.
    """
    result = await call_whisper_native(session, wav_bytes)
    if result:
        text = (result.get("text") or "").strip()
        segments = result.get("segments") or []
        if text or segments:
            return result
        logger.debug("Native Whisper boş döndü, Python Whisper deneniyor.")
    else:
        logger.debug("Native Whisper erişilemedi, Python Whisper deneniyor.")

    loop = asyncio.get_event_loop()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        result = await loop.run_in_executor(_EXECUTOR, _transcribe_pywhisper, path)
        return result
    finally:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


def parse_whisper_response(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    """
    Whisper verbose_json yanıtından:
    - finals: Kesinleşmiş cümle parçaları (client’a "final" gönderilecek)
    - partials: Son/geçici parça (client’a "partial" gönderilecek)
    """
    finals: list[str] = []
    partials: list[str] = []
    segments = result.get("segments") or []
    full_text = (result.get("text") or "").strip()

    if len(segments) > 1:
        for i in range(len(segments) - 1):
            seg = segments[i]
            t = (seg.get("text") or "").strip()
            if t and not should_skip(t):
                finals.append(t)
        last = (segments[-1].get("text") or "").strip()
        if last and not should_skip(last):
            partials.append(last)
    elif full_text and not should_skip(full_text):
        partials.append(full_text)

    return finals, partials


# -----------------------------------------------------------------------------
# FastAPI uygulaması
# -----------------------------------------------------------------------------
app = FastAPI(title="Offline ASR Stream")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    """Tek WebSocket oturumu: ses alır, Whisper’a gönderir, partial/final döner."""
    await websocket.accept()
    logger.info("İstemci bağlandı")

    buffer = bytearray()
    stopped = False

    async def receive_loop() -> None:
        nonlocal stopped
        try:
            while not stopped:
                try:
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.25)
                    buffer.extend(data)
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    stopped = True
                    return
        except Exception as e:
            logger.exception("Ses alma hatası: %s", e)
            stopped = True

    async def process_loop() -> None:
        nonlocal stopped
        async with aiohttp.ClientSession() as session:
            while not stopped:
                if len(buffer) < CHUNK_BYTES:
                    await asyncio.sleep(0.06)
                    continue

                chunk = bytes(buffer[:CHUNK_BYTES])
                del buffer[:CHUNK_BYTES]

                wav_bytes = build_wav(chunk)
                result = await call_whisper(session, wav_bytes)
                if result is None:
                    continue

                finals, partials = parse_whisper_response(result)
                try:
                    for t in finals:
                        await websocket.send_json({"type": "final", "text": t})
                    for t in partials:
                        await websocket.send_json({"type": "partial", "text": t})
                except Exception as e:
                    logger.warning("İstemciye gönderim hatası: %s", e)
                    stopped = True

    receiver = asyncio.create_task(receive_loop())
    try:
        await process_loop()
    finally:
        stopped = True
        receiver.cancel()
        try:
            await receiver
        except asyncio.CancelledError:
            pass
    logger.info("İstemci ayrıldı")


# -----------------------------------------------------------------------------
# Giriş noktası
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info",
    )
