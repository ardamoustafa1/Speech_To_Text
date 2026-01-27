/**
 * WhatsApp-Style Native ASR Widget
 * ------------------------------------------------
 * Entegre etmek için:
 * 1. Bu dosyayı projenize ekleyin.
 * 2. Kodunuzda şu şekilde başlatın:
 * 
 *    const asr = new NativeASR({
 *        inputElement: document.getElementById('chatInput'),
 *        micButton: document.getElementById('micBtn'),
 *        onStatusChange: (status) => console.log(status), // 'listening', 'stopped'
 *        onError: (err) => console.error(err)
 *    });
 *    
 *    asr.init();
 */

class NativeASR {
    constructor(config) {
        this.input = config.inputElement;
        this.micBtn = config.micButton;
        this.onStatusChange = config.onStatusChange || (() => { });
        this.onError = config.onError || (() => { });
        this.lang = config.lang || 'tr-TR';

        this.recognition = null;
        this.isListening = false;
        this.finalTranscript = '';
    }

    init() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.error("Browser does not support Web Speech API");
            this.micBtn.style.display = 'none'; // Hide mic if not supported
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();

        // WhatsApp-like behavior settings
        this.recognition.continuous = true;      // Keep listening even if user pauses
        this.recognition.interimResults = true;  // Show "Ghost text" while speaking

        this.recognition.lang = this.lang;

        this._bindEvents();
        this._bindMicClick();
    }

    _bindEvents() {
        this.recognition.onstart = () => {
            this.isListening = true;
            this.micBtn.classList.add('active'); // You can style .active class in CSS
            this.onStatusChange('listening');
        };

        this.recognition.onend = () => {
            this.isListening = false;
            this.micBtn.classList.remove('active');
            this.onStatusChange('stopped');
        };

        this.recognition.onresult = (event) => {
            let interimTranscript = '';

            // Re-calculate final transcript from the session
            // Note: In a real chat input, you might want to append to existing text
            // Here we assume "Dictation Mode" where you are filling the input.

            let currentFinal = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    currentFinal += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            // Append logic (handle correctly if input is input or div)
            if (this.input.tagName === 'INPUT' || this.input.tagName === 'TEXTAREA') {
                // For Inputs
                this._updateInputVal(currentFinal, interimTranscript);
            } else {
                // For ContentEditable Divs
                this.input.innerHTML = this.finalTranscript + currentFinal +
                    `<span style="color:#999; font-style:italic;">${interimTranscript}</span>`;

                if (currentFinal) this.finalTranscript += currentFinal + " ";
            }
        };

        this.recognition.onerror = (event) => {
            if (event.error === 'no-speech') {
                return; // Ignore silence errors
            }
            this.onError(event.error);
            this.stop();
        };
    }

    _updateInputVal(finalChunk, interimChunk) {
        // Complex logic to handle cursor position is skipped for simplicity.
        // We just append to end for this demo.

        // Note: 'finalTranscript' variable holds the session text
        if (finalChunk) {
            this.finalTranscript += finalChunk + " ";
        }

        // Show: Session Final + Current Interim
        this.input.value = this.finalTranscript + interimChunk;
    }

    _bindMicClick() {
        this.micBtn.addEventListener('click', () => {
            if (this.isListening) {
                this.stop();
            } else {
                // If input has text, maybe keep it?
                this.finalTranscript = (this.input.value || this.input.innerText).trim() + " ";
                if (this.finalTranscript === " ") this.finalTranscript = "";

                this.start();
            }
        });
    }

    start() {
        try {
            this.recognition.start();
        } catch (e) {
            console.warn("Already started", e);
        }
    }

    stop() {
        this.recognition.stop();
    }
}
