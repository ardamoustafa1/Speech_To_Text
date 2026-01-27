/**
 * WhatsApp-Quality Speech-to-Text Client (Robust Version)
 */

class SpeechToText {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl || `ws://${window.location.host}/ws/transcribe`;

        // UI Callbacks
        this.onTranscription = options.onTranscription || (() => { });
        this.onRecordingStart = options.onRecordingStart || (() => { });
        this.onRecordingStop = options.onRecordingStop || (() => { });
        this.onError = options.onError || ((err) => alert(`HATA: ${err}`)); // Alert user directly
        this.onAudioLevel = options.onAudioLevel || (() => { });
        this.onStatusChange = options.onStatusChange || (() => { });

        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.ws = null;

        // Initialize WebSocket immediately
        this._initWebSocket();
    }

    _initWebSocket() {
        try {
            this.ws = new WebSocket(this.wsUrl);
            this.ws.onopen = () => {
                console.log('✅ WebSocket connected');
                this.onStatusChange('connected');
            };
            this.ws.onmessage = (event) => {
                try {
                    const result = JSON.parse(event.data);
                    if (result.success) {
                        this.onTranscription(result.text, result.language);
                    } else {
                        console.error("Server Error:", result.error);
                        // Don't alert for every server error to avoid spam, but log it
                    }
                } catch (e) {
                    console.error('Invalid response:', e);
                }
            };
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.onStatusChange('disconnected');
                setTimeout(() => this._initWebSocket(), 3000);
            };
            this.ws.onerror = (e) => {
                console.error("WebSocket Error:", e);
                this.onStatusChange('error');
            };
        } catch (e) {
            console.error(e);
        }
    }

    async startRecording() {
        if (this.isRecording) return;

        try {
            console.log('Requesting microphone access...');

            // 1. Get Stream
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true
            });

            // 2. Setup Recorder (Let browser choose best format)
            try {
                // Try to use MP4 for Safari if available, otherwise default
                if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    this.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/mp4' });
                } else if (MediaRecorder.isTypeSupported('audio/webm')) {
                    this.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                } else {
                    this.mediaRecorder = new MediaRecorder(stream);
                }
            } catch (e) {
                console.warn("Format selection failed, using default:", e);
                this.mediaRecorder = new MediaRecorder(stream);
            }

            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstart = () => {
                this.isRecording = true;
                this.onRecordingStart();
                this.onStatusChange('recording');
                console.log(`🎤 Recording started (${this.mediaRecorder.mimeType})`);
            };

            this.mediaRecorder.start();

            // 3. Setup Visualization (Optional, silence errors)
            this._setupVisualizer(stream);

        } catch (error) {
            console.error('Recording failed:', error);
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                this.onError('Mikrofon izni reddedildi. Lütfen tarayıcı ve sistem ayarlarından izin verin.');
            } else if (error.name === 'NotFoundError') {
                this.onError('Mikrofon bulunamadı.');
            } else {
                this.onError(`Kayıt başlatılamadı: ${error.message}`);
            }
        }
    }

    async stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) return;

        return new Promise((resolve) => {
            this.mediaRecorder.onstop = () => {
                setTimeout(async () => {
                    await this._sendAudio();
                    resolve();
                }, 200);
            };

            this.mediaRecorder.stop();
            this.isRecording = false;
            this.onRecordingStop();
            this.onStatusChange('processing');

            // Stop tracks
            if (this.mediaRecorder.stream) {
                this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
        });
    }

    async _sendAudio() {
        if (this.audioChunks.length === 0) {
            console.error("No audio chunks recorded");
            // Only alert if there was supposed to be a recording
            return;
        }

        const mimeType = this.mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(this.audioChunks, { type: mimeType });
        console.log(`📤 Sending ${audioBlob.size} bytes (${mimeType})`);

        if (audioBlob.size < 500) {
            console.warn("Audio too short, skipping");
            return;
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // Protocol: Metadata JSON -> Binary
            this.ws.send(JSON.stringify({ mimeType: mimeType }));
            const buffer = await audioBlob.arrayBuffer();
            this.ws.send(buffer);
        } else {
            this.onError("Sunucuya bağlı değil. Lütfen sayfayı yenileyin.");
        }
    }

    _setupVisualizer(stream) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
            const source = this.audioContext.createMediaStreamSource(stream);
            const analyser = this.audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const buffer = new Uint8Array(analyser.frequencyBinCount);

            const draw = () => {
                if (!this.isRecording) return;
                analyser.getByteFrequencyData(buffer);
                const avg = buffer.reduce((a, b) => a + b) / buffer.length;
                this.onAudioLevel(avg / 128); // 0-1
                requestAnimationFrame(draw);
            };
            draw();
        } catch (e) {
            console.warn("Visualizer error:", e);
        }
    }
}

window.SpeechToText = SpeechToText;
