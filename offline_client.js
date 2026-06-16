/**
 * OfflineASR – Profesyonel tarayıcı tarafı ses tanıma istemcisi
 *
 * - Mikrofonu 16 kHz mono PCM’e çevirir (resample + quantize)
 * - WebSocket ile sunucuya gönderir, partial/final metinleri alır
 * - Sonucu contenteditable/input alanında gösterir
 */
(function (global) {
    'use strict';

    const TARGET_RATE = 16000;
    const PROCESSOR_SIZE = 4096;
    const MAX_RECONNECT = 5;
    const RECONNECT_DELAY_MS = 1000;

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : String(str);
        return div.innerHTML;
    }

    /**
     * Float32 mono sesi 16 kHz Int16 PCM’e resample eder.
     * Oran farklıysa doğrusal enterpolasyon kullanır (aliasing azaltır).
     */
    function resampleTo16k(float32, inRate) {
        if (inRate === TARGET_RATE) {
            const out = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
                const s = Math.max(-1, Math.min(1, float32[i]));
                out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            return out;
        }
        const ratio = inRate / TARGET_RATE;
        const outLen = Math.floor(float32.length / ratio);
        const out = new Int16Array(outLen);
        for (let i = 0; i < outLen; i++) {
            const srcIndex = i * ratio;
            const i0 = Math.floor(srcIndex);
            const i1 = Math.min(i0 + 1, float32.length - 1);
            const frac = srcIndex - i0;
            let sample = float32[i0] * (1 - frac) + float32[i1] * frac;
            sample = Math.max(-1, Math.min(1, sample));
            out[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        }
        return out;
    }

    class OfflineASR {
        constructor(options) {
            this.inputEl = options.inputElement;
            this.micBtn = options.micButton || null;
            this.onStatusChange = options.onStatusChange || (function () {});
            this.onError = options.onError || (function () {});
            this.wsUrl = options.wsUrl || 'ws://localhost:8002/ws/transcribe';

            this._listening = false;
            this._finalText = '';
            this._partialText = '';
            this._reconnectCount = 0;

            this._ctx = null;
            this._stream = null;
            this._ws = null;
            this._processor = null;
        }

        get isListening() {
            return this._listening;
        }

        get finalTranscript() {
            return this._finalText;
        }

        init() {
            return;
        }

        _render() {
            const final = (this._finalText || '').trim();
            const partial = (this._partialText || '').trim();

            const isDiv = this.inputEl.tagName === 'DIV' || this.inputEl.tagName === 'SPAN';
            if (isDiv) {
                if (final && partial) {
                    this.inputEl.innerHTML = escapeHtml(final) + ' ' +
                        '<span class="offline-partial">' + escapeHtml(partial) + '</span>';
                } else if (final) {
                    this.inputEl.textContent = final;
                } else if (partial) {
                    this.inputEl.innerHTML = '<span class="offline-partial">' + escapeHtml(partial) + '</span>';
                } else {
                    this.inputEl.textContent = '';
                }
            } else {
                this.inputEl.value = (final + (partial ? ' ' + partial : '')).trim();
            }
            this.inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }

        _onMessage(data) {
            const type = data.type;
            let text = (data.text != null ? data.text : '').trim();
            if (!text) return;

            if (type === 'final') {
                this._finalText += text + ' ';
                this._partialText = '';
            } else {
                this._partialText = text;
            }
            this._render();
        }

        _connect() {
            const ws = new WebSocket(this.wsUrl);
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                this._listening = true;
                this._reconnectCount = 0;
                if (this.micBtn) this.micBtn.classList.add('active');
                this.onStatusChange('listening');
                this._startCapture();
            };

            ws.onmessage = (ev) => {
                try {
                    const data = JSON.parse(ev.data);
                    if (data && typeof data.type === 'string') {
                        this._onMessage(data);
                    }
                } catch (e) {
                    console.warn('OfflineASR: invalid message', e);
                }
            };

            ws.onclose = () => {
                if (this._listening && this._reconnectCount < MAX_RECONNECT) {
                    this._reconnectCount += 1;
                    setTimeout(() => this._connect(), RECONNECT_DELAY_MS);
                } else if (this._listening) {
                    this.stop();
                    this.onError('Sunucu bağlantısı kesildi.');
                }
            };

            ws.onerror = () => {
                if (!this._listening) {
                    this.onError('Sunucuya bağlanılamıyor. (Port 8002 açık mı?)');
                }
            };

            this._ws = ws;
        }

        _startCapture() {
            if (!this._ctx || !this._stream) return;
            const source = this._ctx.createMediaStreamSource(this._stream);
            const proc = this._ctx.createScriptProcessor(PROCESSOR_SIZE, 1, 1);
            const inputRate = this._ctx.sampleRate;

            proc.onaudioprocess = (ev) => {
                if (!this._listening || !this._ws || this._ws.readyState !== WebSocket.OPEN) return;
                const channel = ev.inputBuffer.getChannelData(0);
                const pcm = resampleTo16k(channel, inputRate);
                try {
                    this._ws.send(pcm.buffer);
                } catch (err) {
                    console.warn('OfflineASR: send error', err);
                }
            };
            source.connect(proc);
            proc.connect(this._ctx.destination);
            this._processor = proc;
        }

        async start() {
            if (this._listening) return;

            try {
                this._ctx = new (window.AudioContext || window.webkitAudioContext)();
                this._stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });
            } catch (e) {
                this.onError('Mikrofon erişimi reddedildi: ' + (e.message || e));
                return;
            }

            this._finalText = '';
            this._partialText = '';
            this._connect();
        }

        stop() {
            if (!this._listening) return;

            this._listening = false;
            if (this.micBtn) this.micBtn.classList.remove('active');
            this.onStatusChange('stopped');

            if (this._ws) {
                try { this._ws.close(); } catch (_) {}
                this._ws = null;
            }
            if (this._processor) {
                try { this._processor.disconnect(); } catch (_) {}
                this._processor = null;
            }
            if (this._stream) {
                this._stream.getTracks().forEach(function (t) { t.stop(); });
                this._stream = null;
            }
            if (this._ctx) {
                this._ctx.close().catch(function () {});
                this._ctx = null;
            }

            const full = (this._finalText + ' ' + this._partialText).replace(/\s+/g, ' ').trim();
            if (this.inputEl.tagName === 'DIV' || this.inputEl.tagName === 'SPAN') {
                this.inputEl.textContent = full;
            } else {
                this.inputEl.value = full;
            }
            this.inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            this._finalText = '';
            this._partialText = '';
        }
    }

    global.OfflineASR = OfflineASR;
})(typeof window !== 'undefined' ? window : this);
