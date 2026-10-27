# 🎬 YouTube Transkript İndirici

YouTube videolarından Türkçe ve İngilizce transkript/altyazı indiren, **GUI** ve **CLI** destekli Python aracı.

## ✨ Özellikler

- 🖥️ **Tkinter GUI** — bağımsız pencere arayüzü
- 📄 **TXT & PDF** çıktı formatları
- 🌐 **Türkçe & İngilizce** altyazı desteği
- 🔄 **Otomatik çeviri** — altyazı yoksa başka dilden çevirir
- 🔁 **Çift motor** — `youtube-transcript-api` → `yt-dlp` yedek fallback
- 📦 **Tek EXE** — Python gerekmez, direkt çalışır

## 🚀 Kullanım

### GUI (pencere ile)
```
YouTubeTranskript.exe
```
veya
```
python ytt.py
```

### Komut Satırı
```bash
# TXT olarak kaydet
python ytt.py https://youtu.be/VIDEO_ID -o transkript.txt -l tr

# PDF olarak kaydet
python ytt.py https://youtu.be/VIDEO_ID -o transkript.pdf -l tr

# İngilizce
python ytt.py https://youtu.be/VIDEO_ID -o output.txt -l en

# Klasöre toplu kaydet (txt + pdf)
python ytt.py https://youtu.be/VIDEO_ID -o ./cikti -l tr,en -f txt,pdf
```

## 📦 Kurulum (Python ile çalıştırmak için)

```bash
pip install youtube-transcript-api yt-dlp reportlab
python ytt.py
```

## 📋 Gereksinimler

| Paket | Sürüm | Amaç |
|-------|-------|------|
| `youtube-transcript-api` | ≥1.0 | Altyazı indirme |
| `yt-dlp` | güncel | Yedek indirici |
| `reportlab` | ≥4.0 | PDF oluşturma |

## 📁 Proje Yapısı

```
yuotubetrankript/
├── ytt.py          # Ana script (GUI + CLI)
├── ytt.spec        # PyInstaller derleme config
└── README.md
```

## 🔨 EXE Derleme

```bash
pip install pyinstaller
pyinstaller --clean ytt.spec
# dist/YouTubeTranskript.exe oluşur
```

## 📄 Lisans

MIT
