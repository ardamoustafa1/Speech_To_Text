# 🎤 WhatsApp-Quality Speech-to-Text System

Modern, yüksek doğruluklu sesli mesaj metne dönüştürme sistemi. OpenAI Whisper tabanlı.

![Demo](https://img.shields.io/badge/Status-Ready-green) ![Python](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Özellikler

- 🎯 **%95+ Doğruluk** - OpenAI Whisper ile endüstri lideri doğruluk
- 🌍 **100+ Dil Desteği** - Türkçe, İngilizce ve daha fazlası
- 🔇 **Gürültü Direnci** - Gürültülü ortamlarda bile mükemmel çalışır
- ⚡ **Hızlı İşleme** - WebSocket ile düşük gecikme
- 📱 **Mobil Uyumlu** - Touch events ile tam mobil destek
- 🎨 **Modern UI** - WhatsApp benzeri arayüz, dark/light mode

## 🚀 Hızlı Başlangıç

### 1. Bağımlılıkları Yükle

```bash
cd /Users/ardamoustafa/Desktop/asr

# Virtual environment oluştur (önerilen)
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

> ⚠️ **Not**: İlk kurulumda Whisper modeli indirilecektir (~150MB base model için)

### 2. Sunucuyu Başlat

```bash
python main.py
```

veya:

```bash
uvicorn main:app --reload --port 8080
```

### 3. Tarayıcıda Aç

```
http://localhost:8080
```

## 📖 Kullanım

1. **Mikrofon İzni**: Tarayıcı mikrofon izni isteyecek, "İzin Ver" deyin
2. **Kayıt Başlat**: Yeşil mikrofon butonuna **basılı tutun**
3. **Konuşun**: Örneğin "Merhaba, nasılsınız?"
4. **Bırakın**: Butonu bırakınca mesaj otomatik gönderilir
5. **Sonuç**: 2-3 saniye içinde metin ekranda görünür

### Klavye Kısayolu
- **Space** tuşuna basılı tutarak da kayıt yapabilirsiniz

## 🔧 Yapılandırma

### Whisper Model Seçimi

Ortam değişkeni ile model değiştirebilirsiniz:

```bash
# Hız için (daha az doğruluk)
WHISPER_MODEL=tiny python main.py

# Varsayılan (dengeli)
WHISPER_MODEL=base python main.py

# Daha iyi doğruluk
WHISPER_MODEL=small python main.py

# En iyi doğruluk (yavaş)
WHISPER_MODEL=medium python main.py
```

| Model | Boyut | Hız | Doğruluk |
|-------|-------|-----|----------|
| tiny | 39MB | ⚡⚡⚡⚡⚡ | ⭐⭐ |
| base | 142MB | ⚡⚡⚡⚡ | ⭐⭐⭐ |
| small | 466MB | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| medium | 1.5GB | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| large | 2.9GB | ⚡ | ⭐⭐⭐⭐⭐ |

## 🔌 API Kullanımı

### REST API

```bash
# Ses dosyası yükle
curl -X POST "http://localhost:8000/api/transcribe" \
  -F "file=@audio.wav"
```

Yanıt:
```json
{
  "success": true,
  "text": "Merhaba, nasılsınız?",
  "language": "tr"
}
```

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/transcribe');

ws.onopen = () => {
  // Ses verisini binary olarak gönder
  ws.send(audioBlob);
};

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  console.log(result.text); // "Merhaba, nasılsınız?"
};
```

## 🔗 Mevcut Projeye Entegrasyon

```javascript
// SpeechToText sınıfını import edin
import { SpeechToText } from './app.js';

// Kendi callback'lerinizi tanımlayın
const stt = new SpeechToText({
  wsUrl: 'ws://your-server:8000/ws/transcribe',
  onTranscription: (text, language) => {
    // Mesajı chat sisteminize gönderin
    yourChatSystem.sendMessage(text);
  },
  onError: (error) => {
    console.error('STT Error:', error);
  }
});

// Mikrofon butonunuza bağlayın
yourMicButton.addEventListener('mousedown', () => stt.startRecording());
yourMicButton.addEventListener('mouseup', () => stt.stopRecording());
```

## 📁 Dosya Yapısı

```
asr/
├── main.py           # FastAPI backend + Whisper
├── app.js            # Frontend JavaScript (SpeechToText class)
├── style.css         # WhatsApp-style CSS
├── index.html        # Demo web arayüzü
├── requirements.txt  # Python bağımlılıkları
└── README.md         # Bu dosya
```

## 🛠️ Geliştirme

```bash
# Development mode (auto-reload)
uvicorn main:app --reload --port 8000 --log-level debug
```

## 📋 Gereksinimler

- Python 3.8+
- FFmpeg (ses dönüşümü için - opsiyonel)
- Modern tarayıcı (Chrome, Firefox, Safari, Edge)

### FFmpeg Kurulumu (Opsiyonel)

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
choco install ffmpeg
```

## 🐛 Sorun Giderme

### "Mikrofon izni verilmedi"
- Tarayıcı ayarlarından mikrofon iznini kontrol edin
- HTTPS veya localhost üzerinden erişin

### "Whisper model yüklenemedi"
- İnternet bağlantınızı kontrol edin
- Yeterli disk alanı olduğundan emin olun

### Yavaş transkripsiyon
- Daha küçük model deneyin: `WHISPER_MODEL=tiny`
- GPU destekli PyTorch yükleyin

## 📄 Lisans

MIT License - İstediğiniz şekilde kullanabilirsiniz.

---

Made with ❤️ using OpenAI Whisper
