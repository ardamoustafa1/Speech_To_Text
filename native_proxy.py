import asyncio
import io
import os
import uvicorn
import requests
import numpy as np
import subprocess
import wave
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Native Server Configuration
NATIVE_HOST = "http://127.0.0.1:8003"

app = FastAPI(title="Native ASR Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected (Native Proxy)")
    
    audio_buffer = bytearray()
    last_processed_len = 0
    is_client_connected = True
    
    async def receive_audio():
        nonlocal is_client_connected
        try:
            while True:
                data = await websocket.receive_bytes()
                # print(f"DEBUG: Received {len(data)} bytes") # Too noisy, better check in transcribe
                audio_buffer.extend(data)
        except:
            is_client_connected = False

    async def transcribe_loop():
        nonlocal last_processed_len
        
        while is_client_connected:
            # Check buffer (every 0.5s)
            current_len = len(audio_buffer)
            if current_len > last_processed_len:
                 pass # DEBUG: print(f"Buffer Size: {current_len}")

            # Wait for at least 0.5 second of audio (~16kB)
            if current_len > last_processed_len and current_len > 32000 * 0.5:
                
                # Prepare WAV file in memory to send to C++ server
                # The C++ server likely accepts multipart/form-data with a file.
                
                try:
                    # Create a temporary WAV bytes
                    # Whisper.cpp server typically expects a standard wav file upload
                    
                    with io.BytesIO() as wav_io:
                        with wave.open(wav_io, "wb") as wav_file:
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2) # 16-bit
                            wav_file.setframerate(16000)
                            wav_file.writeframes(audio_buffer)
                        
                        wav_bytes = wav_io.getvalue()
                        print(f"Sending {len(wav_bytes)} bytes to Native Engine...")
                        
                        # Send to Native Server
                        # Running in thread to avoid blocking async loop
                        loop = asyncio.get_event_loop()
                        
                        # Assuming the native server follows OAI or customized endpoint
                        # Whisper.cpp 'server' example usually has "/inference"
                        
                        def send_request():
                            files = {
                                'file': ('blob.wav', wav_bytes, 'audio/wav')
                            }
                            # Basic params
                            data = {
                                'temperature': '0.0',
                                'response_format': 'json',
                                'language': 'tr',
                                'prompt': 'Merhaba, şu an Türkçe konuşuyorum. Noktalama işaretlerine dikkat edelim.'
                            }
                            # Verify if we should use /inference or /v1/audio/transcriptions
                            # Whisper.cpp server example recently supports /inference
                            try:
                                return requests.post(f"{NATIVE_HOST}/inference", files=files, data=data, timeout=5)
                            except Exception as e:
                                print(f"Request Error: {e}")
                                return None

                        response = await loop.run_in_executor(None, send_request)
                        
                        if response and response.status_code == 200:
                            res_json = response.json()
                            # response format usually: {"text": "..."}
                            text = res_json.get("text", "").strip()
                            
                            if text:
                                await websocket.send_json({
                                    "type": "partial",
                                    "text": text
                                })
                                last_processed_len = current_len

                except Exception as e:
                    print(f"Proxy Error: {e}")
            
            await asyncio.sleep(0.4)

    await asyncio.gather(receive_audio(), transcribe_loop())
    print("Client disconnected")

if __name__ == "__main__":
    # Run on port 8002 (as expected by client)
    uvicorn.run(app, host="0.0.0.0", port=8002)
