"""
WhatsApp-Quality Speech-to-Text API (Pro GPU Edition)
=====================================================
Powered by OpenAI Whisper with Apple Silicon (MPS) Acceleration.
"""

import os
import tempfile
import asyncio
import logging
import ssl
import json
import subprocess
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

# Fix for SSL
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import whisper
import torch

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global Model
whisper_model = None
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small") # Default start
DEVICE = "cpu"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load Whisper model with Auto-GPU Detection."""
    global whisper_model, MODEL_SIZE, DEVICE
    
    # Check for Apple Silicon (MPS)
    if torch.backends.mps.is_available():
        DEVICE = "mps"
        # Use 'small' model on GPU for perfect balance of speed/accuracy
        MODEL_SIZE = "small" 
        logger.info(f"🚀 Apple Silicon GPU Detected! Using '{MODEL_SIZE}' model for blazing speed.")
    elif torch.cuda.is_available():
        DEVICE = "cuda"
        MODEL_SIZE = "small"
        logger.info(f"🚀 NVIDIA GPU Detected! Using '{MODEL_SIZE}' model.")
    else:
        DEVICE = "cpu"
        MODEL_SIZE = "small" # Keep small for CPU speed
        logger.info("ℹ️ Running on CPU. Using optimized 'small' model.")

    logger.info(f"🔄 Loading Whisper model '{MODEL_SIZE}' on {DEVICE.upper()}...")
    
    try:
        whisper_model = whisper.load_model(MODEL_SIZE, device=DEVICE)
        logger.info("✅ Model loaded and ready!")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise
    
    yield
    whisper_model = None

app = FastAPI(title="ASR Pro", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

def convert_to_wav(input_path: str) -> str:
    """Sanitize audio to 16kHz WAV."""
    output_path = input_path + ".clean.wav"
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_path
    except Exception as e:
        logger.error(f"FFmpeg error: {e}")
        return input_path # Fallback to original

def transcribe_audio(audio_path: str, language: str = "tr") -> dict:
    global whisper_model
    if not whisper_model: raise RuntimeError("Model not loaded")
    
    clean_path = convert_to_wav(audio_path)
    
    try:
        # Options optimized for accuracy
        options = {
            "language": language,
            "task": "transcribe",
            "fp16": False # Safe for generic compatibility
        }
        
        # If using GPU, we can enable more expensive features
        if DEVICE != "cpu":
            options.update({
                "beam_size": 5,
                "best_of": 5,
                "patience": 1.0,
                "temperature": 0.0
            })
            
        result = whisper_model.transcribe(clean_path, **options)
        
        return {
            "success": True,
            "text": result["text"].strip(),
            "language": result.get("language", "unknown")
        }
    except Exception as e:
        logger.error(f"Transcribe failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if clean_path != audio_path and os.path.exists(clean_path):
            try: os.unlink(clean_path)
            except: pass

@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    temp_file = Path(tempfile.gettempdir()) / f"rec_{client_id}.webm"
    
    try:
        while True:
            data = await websocket.receive_bytes()
            # Overwrite mode for atomic blobs
            with open(temp_file, "wb") as f:
                f.write(data)

            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: transcribe_audio(str(temp_file)))
            await websocket.send_json(res)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS Error: {e}")
    finally:
        if temp_file.exists():
            try: os.unlink(temp_file)
            except: pass

if __name__ == "__main__":
    import uvicorn
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     🎤 Server Running on Port 9000 (GPU Mode)            ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Web UI:   http://localhost:9000                         ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=False)
