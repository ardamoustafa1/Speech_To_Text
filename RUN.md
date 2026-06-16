# Sistemi Çalıştırma

**Terminal.app** veya **iTerm** ile aşağıdakileri kendi bilgisayarında çalıştır.

---

## En kolay yol: Sadece Python (C++ / model indirmeden)

Offline modda **hiçbir şey algılanmıyor** diyorsan bu yöntem çoğu zaman yeterli olur. C++ Whisper sunucusu (8003) gerekmez; proxy kendi içinde **Python Whisper** kullanır.

1. Bağımlılıkları yükle (ilk seferde Whisper modeli indirilir, ~150 MB):
   ```bash
   cd /Users/ardamoustafa/Desktop/asr
   pip install -r requirements.txt
   ```
2. Sadece **iki** servisi başlat (Whisper 8003 açmayın):
   ```bash
   python3 native_streaming_server.py
   ```
   Başka bir terminalde:
   ```bash
   python3 -m http.server 8080
   ```
3. Tarayıcıda **http://localhost:8080** aç, OFFLINE modu seç, mikrofonu kullan.

İlk konuşmada model yükleneceği için 30–60 saniye bekleyebilirsin; sonraki konuşmalar daha hızlıdır.

---

## Tek komut (C++ Whisper ile)

```bash
cd /Users/ardamoustafa/Desktop/asr
./start_servers.sh
```

Bu script:
1. **Whisper sunucusu** (8003) – sesi metne çevirir  
2. **Streaming proxy** (8002) – tarayıcı ↔ Whisper arası köprü  
3. **Web sunucusu** (8080) – arayüzü sunar  

Tarayıcı otomatik açılmazsa adres: **http://localhost:8080**

---

## Adım adım

Üç pencerede sırayla:

**Terminal 1 – Whisper**
```bash
cd /Users/ardamoustafa/Desktop/asr/native_asr
./build/bin/whisper-server --host 127.0.0.1 --port 8003 -m models/for-tests-ggml-base.bin -l tr -ng
```

**Terminal 2 – Proxy**
```bash
cd /Users/ardamoustafa/Desktop/asr
python3 native_streaming_server.py
```

**Terminal 3 – Web**
```bash
cd /Users/ardamoustafa/Desktop/asr
python3 -m http.server 8080
```

Sonra tarayıcıda: **http://localhost:8080**

---

## Offline mod: Whisper başlamıyorsa / 8003 connection refused

`ggml-small.bin` bazen “not all tensors loaded” hatası verebilir. Tam model indirmek için:

```bash
cd /Users/ardamoustafa/Desktop/asr/native_asr/models
bash download-ggml-model.sh base
```

İndirilen `ggml-base.bin` ile Whisper’ı başlat:

Sonra tekrar `./start_servers.sh` çalıştır; script `ggml-base.bin` varsa onu kullanır.

**Önemli:** `for-tests-ggml-base.bin` ile sunucu açılır ama **hiç metin üretmez**. Offline modda ekranda metin görmek için mutlaka yukarıdaki komutla `ggml-base.bin` indirin.
