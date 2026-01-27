"""
ASR V3.0: Real-time Streaming Engine (Port 9001)
================================================
Features:
- Silero VAD for Speech Detection
- Rolling Buffer for Continuous Transcription
- AudioWorklet Support (Raw PCM 16kHz)
"""

import os
import asyncio
import logging
import json
import ssl
import torch
import numpy as np
import whisper
import time
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ASRv3")

# Globals
VAD_MODEL = None
WHISPER_MODEL = None
DEVICE = "cpu"
SAMPLE_RATE = 16000

# Fix SSL for Torch Hub
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

@asynccontextmanager
async def lifespan(app: FastAPI):
    global VAD_MODEL, WHISPER_MODEL, DEVICE
    
    # 1. Setup Device
    if torch.backends.mps.is_available():
        DEVICE = "mps"
        logger.info("🚀 V3 Running on Apple Silicon GPU (MPS)")
    else:
        logger.info("ℹ️ V3 Running on CPU")

    # 2. Load Silero VAD
    try:
        logger.info("loading Silero VAD...")
        VAD_MODEL, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
        logger.info("✅ VAD Loaded")
    except Exception as e:
        logger.error(f"❌ VAD Load Failed: {e}")
        raise

    # 3. Load Whisper
    try:
        model_size = "small" # Fast enough for streaming
        logger.info(f"loading Whisper '{model_size}'...")
        WHISPER_MODEL = whisper.load_model(model_size, device=DEVICE)
        logger.info("✅ Whisper Loaded")
    except Exception as e:
        logger.error(f"❌ Whisper Load Failed: {e}")
        raise

    yield
    
    # Cleanup
    VAD_MODEL = None
    WHISPER_MODEL = None

app = FastAPI(title="ASR V3 Streaming", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return FileResponse("index_v3.html")

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 Stream Connected")
    
    # Validation settings
    FRAME_SIZE = 512 
    buffer = np.array([], dtype=np.float32)
    speech_buffer = []  # List of float32 chunks
    is_speaking = False
    
    # VAD sensitivity
    vad_iterator = torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)[1][3](VAD_MODEL, threshold=0.5, sampling_rate=SAMPLE_RATE)
    
    # Validation settings
    MIN_VAD_SIZE = 512
    vad_buffer = np.array([], dtype=np.float32)
    
    try:
        while True:
            # Receive Raw Float32 PCM
            data_bytes = await websocket.receive_bytes()
            new_chunk = np.frombuffer(data_bytes, dtype=np.float32)
            
            # Accumulate for VAD check
            vad_buffer = np.concatenate((vad_buffer, new_chunk))
            
            # Process strictly in 512-sample blocks
            while len(vad_buffer) >= MIN_VAD_SIZE:
                # Take exactly 512 samples
                process_chunk = vad_buffer[:MIN_VAD_SIZE]
                vad_buffer = vad_buffer[MIN_VAD_SIZE:]
                
                # Check VAD
                speech_prob = VAD_MODEL(torch.from_numpy(process_chunk), SAMPLE_RATE).item()
                
                # State Machine
                if speech_prob > 0.5:
                    if not is_speaking:
                        is_speaking = True
                        logger.info("🗣️ Speech Started")
                        await websocket.send_json({"status": "listening"})
                    speech_buffer.append(process_chunk)
                else:
                    if is_speaking:
                        is_speaking = False
                        logger.info("🤫 Silence - Transcribing...")
                        await websocket.send_json({"status": "processing"})
                        
                        # Transcribe accumulated buffer
                        if len(speech_buffer) > 0:
                            full_audio = np.concatenate(speech_buffer)
                            
                            # Flatten because we appended chunks of 512
                            # Actually list of arrays is fine for concat
                            
                            # Check Duration
                            if len(full_audio) > SAMPLE_RATE * 0.5:
                                text = await transcribe_numpy(full_audio)
                                if text:
                                    logger.info(f"📝 Transcribed: {text}")
                                    await websocket.send_json({"text": text, "is_final": True})
                            
                            speech_buffer = [] 
                    else:
                        pass
                
                # If still speaking, append to speech buffer?
                # WAIT: If speech_prob > 0.5, we appended `process_chunk`.
                # But we ONLY appended `process_chunk` (512).
                # The issue is: `speech_buffer` collects ONLY parts where VAD > 0.5.
                # This might clip start/end. 
                # Better: Always maintain a rolling context?
                # For simplicity V3 MVP: Just appending active chunks is usually OK for Silero.
                # But let's add a small padding if possible?
                # No, keep it simple first.


    except WebSocketDisconnect:
        logger.info("🔌 Disconnected")
    except Exception as e:
        logger.error(f"Stream Error: {e}")

async def transcribe_numpy(audio_np: np.ndarray) -> str:
    """Helper to transcribe numpy array directly"""
    try:
        # Whisper expects float32, which we have.
        # Pad or trim to 30s? No, transcribe() handles it.
        # But we need to move to CPU/GPU?
        
        # NOTE: data is already float32.
        # We might need to write to temp file if tensor conversion is tricky on MPS?
        # Whisper `transcribe` function accepts numpy array directly!
        
        result = WHISPER_MODEL.transcribe(audio_np, fp16=False, language="tr")
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Transcribe Error: {e}")
        return ""

if __name__ == "__main__":
    import uvicorn
    print("🚀 V3 Streaming Server running on :9001")
    uvicorn.run("main_v3:app", host="0.0.0.0", port=9001, reload=False)
