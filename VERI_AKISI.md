# Veri akışı: Hangi sunucu / servise nereye gidiyor?

Bu belge, projedeki **Online** ve **Offline** ses tanıma modlarında verinin (ses ve metin) hangi IP, sunucu veya servise gittiğini açıklar.

---

## 1. Online mod (Google – Web Speech API)

### Kullanılan kod
- **Dosya:** `native_asr.js`
- **API:** `SpeechRecognition` / `webkitSpeechRecognition` (tarayıcı yerleşik)

### Veri nereye gidiyor?
- Ses **doğrudan tarayıcı (Chrome/Edge) içinden** Google altyapısına gönderilir.
- Senin yazdığın kod **hiçbir sunucu adresi veya IP içermez**; bağlantı tamamen tarayıcı tarafından yapılır.

### Google tarafı (araştırma özeti)
| Konu | Açıklama |
|------|----------|
| **Hedef** | Google’ın ses tanıma servisleri (Chrome, bu API için kendi anahtarıyla bağlanır). |
| **Resmî dokümantasyon** | Tam endpoint adresi Web Speech API için açıklanmıyor; “Chrome sesi Google’a gönderir” ifadesi kullanılıyor. |
| **Google Cloud ile fark** | Ücretli **Cloud Speech-to-Text** için bölgesel endpoint’ler açık: `https://us-speech.googleapis.com`, `https://eu-speech.googleapis.com`. Tarayıcıdaki **ücretsiz Web Speech API** muhtemelen farklı / dahili endpoint’ler kullanır; detay resmî olarak yayımlanmıyor. |
| **Gönderilen veriler** | Ses kaydı, sitenin **domain**’i, tarayıcı/site **dil ayarları**. İsteklerle **çerez gönderilmediği** belirtiliyor. |
| **Gizlilik** | Chrome Privacy Whitepaper’da ses verisinin bu API ile nasıl işlendiği anlatılıyor. Google, belirli bağlamlarda (ör. yönetilen ChromeOS) “Speech-to-Text kullanımında kişisel veri toplanmıyor” diyor; tarayıcıdaki genel Web Speech API için de veri Google sunucularında işlenir. |

### Özet (Online)
- **IP / sunucu:** Google’a ait sunucular (tam adres tarayıcı içinde, dokümante edilmiyor).
- **Senin sunucun:** Devreye girmiyor; sadece tarayıcı ↔ Google iletişimi var.
- **İnternet:** Gerekli; offline çalışmaz.

---

## 2. Offline mod (kendi sunucumuz)

### Kullanılan kod
- **İstemci:** `offline_client.js`, `index.html` (WebSocket adresi)
- **Sunucu:** `native_streaming_server.py` (proxy + isteğe bağlı Python Whisper)

### Adım adım veri akışı

| Adım | Kaynak | Hedef | Adres / Açıklama |
|------|--------|--------|-------------------|
| 1 | Tarayıcı (senin PC) | Proxy (aynı PC) | **WebSocket:** `ws://localhost:8002/ws/transcribe` → gerçekte **127.0.0.1:8002** |
| 2a | Proxy (Python) | C++ Whisper (varsa) | **HTTP:** `http://127.0.0.1:8003/inference` → yine **127.0.0.1:8003** (aynı makine) |
| 2b | Proxy (Python) | Yok (işlem içi) | C++ yoksa veya cevap boşsa **Python Whisper** aynı process içinde çalışır; **hiçbir ağ isteği yok** |

### Projede geçen adresler (grep sonucu)
- `offline_client.js`: `wsUrl: 'ws://localhost:8002/ws/transcribe'` (varsayılan)
- `index.html`: `wsUrl: 'ws://localhost:8002/ws/transcribe'`
- `native_streaming_server.py`: `WHISPER_URL = "http://127.0.0.1:8003/inference"`, `SERVER_PORT = 8002`

### Özet (Offline)
- **Tüm trafik yerel:** Sadece **localhost (127.0.0.1)**; port **8002** (proxy) ve isteğe bağlı **8003** (C++ Whisper).
- **Dış IP / internet:** Kullanılmıyor; ses dışarı çıkmıyor.

---

## 3. Karşılaştırma

| Mod | Verinin gittiği yer | İnternet | Senin sunucun |
|-----|---------------------|----------|----------------|
| **Online** | Google’ın ses tanıma servisleri (tarayıcı üzerinden) | Evet | Hayır |
| **Offline** | Sadece 127.0.0.1:8002 ve 127.0.0.1:8003 (veya sadece 8002’de Python) | Hayır | Evet (kendi makinen) |

---

## 4. Referanslar (araştırma)

- Chrome, Web Speech API: [Voice driven web apps - Introduction to the Web Speech API](https://developer.chrome.com/blog/voice-driven-web-apps-introduction-to-the-web-speech-api)  
- Chrome ses verisi: [Chrome Privacy Whitepaper – speech](https://www.google.com/chrome/privacy/whitepaper.html#speech)  
- Mozilla, Web Speech API: [Web Speech API - Speech Recognition](https://wiki.mozilla.org/Web_Speech_API_-_Speech_Recognition)  
- Stack Overflow: Chrome/Edge’de Web Speech API’nin offsite (Google) sunucu kullanması  
- Google Cloud (karşılaştırma için): [Speech-to-Text endpoints](https://cloud.google.com/speech-to-text/docs/endpoints) (`us-speech.googleapis.com`, `eu-speech.googleapis.com`)
