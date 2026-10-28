import argparse
import html
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path


DEFAULT_LANGUAGES = ("tr", "en")
LANGUAGE_NAMES = {
    "tr": "Türkçe",
    "en": "İngilizce",
}
DEFAULT_FORMATS = ("txt", "pdf")


class TranscriptError(Exception):
    pass


def video_id_ayikla(video_url):
    video_url = video_url.strip()

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_url):
        return video_url

    parsed = urllib.parse.urlparse(video_url)

    if parsed.netloc.endswith("youtu.be"):
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return video_id

    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            query = urllib.parse.parse_qs(parsed.query)
            if query.get("v"):
                return query["v"][0]

        shorts_match = re.match(r"^/(shorts|embed|live)/([^/?#]+)", parsed.path)
        if shorts_match:
            return shorts_match.group(2)

    raise TranscriptError("Video ID bulunamadı. YouTube URL'sini veya 11 karakterlik video ID'yi ver.")


def dosya_adi_temizle(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return value[:120] or "transkript"


def parcalari_duz_metne_cevir(parcalar):
    metinler = []
    onceki = None

    for parca in parcalar:
        text = None
        if isinstance(parca, dict):
            text = parca.get("text") or parca.get("utf8")
        else:
            text = getattr(parca, "text", None)

        if not text:
            continue

        text = html.unescape(text).replace("\n", " ").strip()
        if text and text != onceki:
            metinler.append(text)
            onceki = text

    return " ".join(" ".join(metinler).split())


def pdf_yaz(output_path, metin, baslik, kaynak):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise TranscriptError("PDF oluşturmak için reportlab kurulu değil.") from exc

    font_name = "Helvetica"
    arial_path = Path(r"C:\Windows\Fonts\arial.ttf")
    if arial_path.exists():
        font_name = "Arial"
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(arial_path)))
        except Exception:
            font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TranscriptTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=16,
        leading=20,
        spaceAfter=12,
    )
    meta_style = ParagraphStyle(
        "TranscriptMeta",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor="#555555",
        spaceAfter=14,
    )
    body_style = ParagraphStyle(
        "TranscriptBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title=baslik,
    )

    story = [
        Paragraph(html.escape(baslik), title_style),
        Paragraph(html.escape(f"Kaynak: {kaynak}"), meta_style),
    ]

    cumleler = re.split(r"(?<=[.!?])\s+", metin)
    paragraf = []
    uzunluk = 0

    for cumle in cumleler:
        paragraf.append(cumle)
        uzunluk += len(cumle)
        if uzunluk >= 900:
            story.append(Paragraph(html.escape(" ".join(paragraf)), body_style))
            paragraf = []
            uzunluk = 0

    if paragraf:
        story.append(Paragraph(html.escape(" ".join(paragraf)), body_style))

    story.append(Spacer(1, 0.2 * cm))
    doc.build(story)


def youtube_transcript_api_ile_dil_indir(video_id, hedef_dil, kaynak_diller=DEFAULT_LANGUAGES, ceviri_dene=True):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise TranscriptError("youtube-transcript-api kurulu değil.") from exc

    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
    except Exception as exc:
        raise TranscriptError(f"Altyazı listesi alınamadı: {exc}") from exc

    try:
        transcript = transcript_list.find_transcript([hedef_dil])
        metin = parcalari_duz_metne_cevir(transcript.fetch())
        if metin:
            kaynak = "manuel" if not transcript.is_generated else "otomatik"
            return metin, f"youtube-transcript-api ({kaynak}: {hedef_dil})"
    except Exception:
        pass

    if not ceviri_dene:
        raise TranscriptError(f"{hedef_dil} altyazısı bulunamadı.")

    once_dene = list(dict.fromkeys([*kaynak_diller, "en", "tr"]))

    adaylar = []
    for diller in (once_dene, None):
        try:
            adaylar.append(transcript_list.find_transcript(diller) if diller else next(iter(transcript_list)))
        except Exception:
            continue

    for transcript in adaylar:
        if transcript.language_code == hedef_dil or not transcript.is_translatable:
            continue

        ceviri_dilleri = {dil.language_code for dil in transcript.translation_languages}
        if hedef_dil not in ceviri_dilleri:
            continue

        try:
            translated = transcript.translate(hedef_dil)
            metin = parcalari_duz_metne_cevir(translated.fetch())
            if metin:
                return metin, f"youtube-transcript-api (çeviri: {transcript.language_code} -> {hedef_dil})"
        except Exception:
            continue

    raise TranscriptError(f"{hedef_dil} için altyazı veya çevrilebilir kaynak bulunamadı.")


def json3_altyazi_indir(altyazi_url):
    if "fmt=" not in altyazi_url:
        ayirici = "&" if "?" in altyazi_url else "?"
        altyazi_url = f"{altyazi_url}{ayirici}fmt=json3"

    request = urllib.request.Request(
        altyazi_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:
        raise TranscriptError(f"Altyazı bağlantısı indirilemedi: {exc}") from exc

    veri = json.loads(payload)
    parcalar = []

    for event in veri.get("events", []):
        parcalar.extend(event.get("segs", []))

    metin = parcalari_duz_metne_cevir(parcalar)
    if not metin:
        raise TranscriptError("yt-dlp altyazı URL'si metin döndürmedi.")

    return metin


def yt_dlp_ile_dil_indir(video_url, hedef_dil):
    try:
        import yt_dlp
    except ImportError as exc:
        raise TranscriptError("yt-dlp kurulu değil.") from exc

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:
        raise TranscriptError(f"yt-dlp video bilgisini alamadı: {exc}") from exc

    captions = info.get("subtitles") or {}
    auto_captions = info.get("automatic_captions") or {}

    for kaynak_adi, kaynak in (("manuel altyazı", captions), ("otomatik altyazı", auto_captions)):
        tracks = kaynak.get(hedef_dil) or []
        json_track = next(
            (
                track
                for track in tracks
                if track.get("ext") == "json3" or "fmt=json3" in track.get("url", "")
            ),
            None,
        )
        if not json_track and tracks:
            json_track = tracks[0]
        if json_track and json_track.get("url"):
            metin = json3_altyazi_indir(json_track["url"])
            return metin, f"yt-dlp ({kaynak_adi}: {hedef_dil})"

    uygun_diller = sorted(set(captions) | set(auto_captions))
    if uygun_diller:
        raise TranscriptError(
            f"{hedef_dil} bulunamadı. Mevcut diller: " + ", ".join(uygun_diller[:30])
        )

    raise TranscriptError("Bu videoda erişilebilir altyazı veya otomatik transkript bulunamadı.")


def tek_dil_transkript_indir(video_url, hedef_dil, ceviri_dene=True):
    video_id = video_id_ayikla(video_url)
    hatalar = []

    for indirici in (
        lambda: youtube_transcript_api_ile_dil_indir(video_id, hedef_dil, DEFAULT_LANGUAGES, ceviri_dene),
        lambda: yt_dlp_ile_dil_indir(video_url, hedef_dil),
    ):
        try:
            return indirici()
        except TranscriptError as exc:
            hatalar.append(str(exc))

    raise TranscriptError(f"{hedef_dil} transkripti alınamadı.\n- " + "\n- ".join(hatalar))


def transkriptleri_indir(video_url, output_dir, diller, ceviri_dene=True, temel_ad=None, formats=DEFAULT_FORMATS):
    video_id = video_id_ayikla(video_url)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    temel_ad = dosya_adi_temizle(temel_ad or video_id)
    formats = tuple(dict.fromkeys(format.lower() for format in formats))
    sonuclar = []
    hatalar = []

    for dil in diller:
        try:
            metin, kaynak = tek_dil_transkript_indir(video_url, dil, ceviri_dene)
            dosyalar = []

            if "txt" in formats:
                txt_path = output_dir / f"{temel_ad}_{dil}.txt"
                txt_path.write_text(metin, encoding="utf-8")
                dosyalar.append(txt_path)

            if "pdf" in formats:
                pdf_path = output_dir / f"{temel_ad}_{dil}.pdf"
                baslik = f"{temel_ad} - {LANGUAGE_NAMES.get(dil, dil)} transkript"
                pdf_yaz(pdf_path, metin, baslik, kaynak)
                dosyalar.append(pdf_path)

            sonuclar.append(
                {
                    "dil": dil,
                    "dosyalar": dosyalar,
                    "kaynak": kaynak,
                    "kelime": len(metin.split()),
                }
            )
        except TranscriptError as exc:
            hatalar.append({"dil": dil, "hata": str(exc)})

    if not sonuclar:
        mesajlar = [f"{hata['dil']}: {hata['hata']}" for hata in hatalar]
        raise TranscriptError("Hiçbir transkript alınamadı.\n- " + "\n- ".join(mesajlar))

    return sonuclar, hatalar


def transkript_indir(video_url, output_dosya_adi="transkript.txt", languages=DEFAULT_LANGUAGES):
    hedef_dil = languages[0] if languages else "tr"
    metin, kaynak = tek_dil_transkript_indir(video_url, hedef_dil, ceviri_dene=True)
    output_path = Path(output_dosya_adi)
    if output_path.suffix.lower() == ".pdf":
        pdf_yaz(output_path, metin, f"{output_path.stem} - {hedef_dil} transkript", kaynak)
    else:
        output_path.write_text(metin, encoding="utf-8")
    print(f"[+] İşlem başarılı. Kaynak: {kaynak}")
    print(f"[+] Kayıt: {output_path.resolve()}")
    print(f"[+] Kelime sayısı: {len(metin.split())}")
    return metin


def gui_baslat():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    root = tk.Tk()
    root.title("YouTube Transkript İndirici Dr. Soner ASLAN")
    root.geometry("760x560")
    root.minsize(680, 500)

    url_var = tk.StringVar()
    output_var = tk.StringVar(value=str(Path.cwd()))
    base_name_var = tk.StringVar()
    tr_var = tk.BooleanVar(value=True)
    en_var = tk.BooleanVar(value=True)
    txt_var = tk.BooleanVar(value=True)
    pdf_var = tk.BooleanVar(value=True)
    translate_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Hazır")

    def log_yaz(mesaj):
        log.configure(state="normal")
        log.insert("end", mesaj + "\n")
        log.see("end")
        log.configure(state="disabled")

    def dosya_ac(event, dosya):
        yol = Path(dosya)
        if not yol.exists():
            messagebox.showerror("Dosya bulunamadı", f"Dosya artık mevcut değil:\n{yol}")
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(yol))
            else:
                webbrowser.open(yol.resolve().as_uri())
        except OSError as exc:
            messagebox.showerror("Dosya açılamadı", f"Dosya açılırken hata oluştu:\n{exc}")

    def log_dosya(dosya):
        yol = Path(dosya)
        etiket = f"dosya_{log.index('end-1c').replace('.', '_')}"
        log.configure(state="normal")
        log.insert("end", "    Dosya: ")
        log.insert("end", str(yol), (etiket,))
        log.insert("end", "\n")
        log.tag_bind(etiket, "<Button-1>", lambda event, hedef=yol: dosya_ac(event, hedef))
        log.tag_bind(etiket, "<Enter>", lambda event: log.configure(cursor="hand2"))
        log.tag_bind(etiket, "<Leave>", lambda event: log.configure(cursor=""))
        log.see("end")
        log.configure(state="disabled")

    def klasor_sec():
        secilen = filedialog.askdirectory(initialdir=output_var.get() or str(Path.cwd()))
        if secilen:
            output_var.set(secilen)

    def indir_baslat():
        url = url_var.get().strip()
        diller = []
        if tr_var.get():
            diller.append("tr")
        if en_var.get():
            diller.append("en")
        formats = []
        if txt_var.get():
            formats.append("txt")
        if pdf_var.get():
            formats.append("pdf")

        if not url:
            messagebox.showwarning("Eksik link", "Önce YouTube video linkini yapıştır.")
            return
        if not diller:
            messagebox.showwarning("Eksik dil", "En az bir dil seç.")
            return
        if not formats:
            messagebox.showwarning("Eksik format", "TXT veya PDF formatlarından en az birini seç.")
            return

        indir_button.configure(state="disabled")
        status_var.set("İndiriliyor...")
        log_yaz("[+] İşlem başladı.")

        def worker():
            try:
                sonuclar, hatalar = transkriptleri_indir(
                    url,
                    output_var.get().strip() or Path.cwd(),
                    diller,
                    ceviri_dene=translate_var.get(),
                    temel_ad=base_name_var.get().strip() or None,
                    formats=formats,
                )

                def basarili():
                    for sonuc in sonuclar:
                        dil_adi = LANGUAGE_NAMES.get(sonuc["dil"], sonuc["dil"])
                        log_yaz(f"[+] {dil_adi}: {sonuc['kelime']} kelime")
                        for dosya in sonuc["dosyalar"]:
                            log_dosya(dosya)
                        log_yaz(f"    Kaynak: {sonuc['kaynak']}")
                    for hata in hatalar:
                        dil_adi = LANGUAGE_NAMES.get(hata["dil"], hata["dil"])
                        log_yaz(f"[!] {dil_adi} indirilemedi: {hata['hata']}")

                    if hatalar:
                        status_var.set("Kısmen tamamlandı")
                        messagebox.showwarning(
                            "Kısmen bitti",
                            "Bazı transkriptler indirildi, bazıları alınamadı. Detaylar işlem günlüğünde.",
                        )
                    else:
                        status_var.set("Tamamlandı")
                        messagebox.showinfo("Bitti", "Seçilen transkriptler indirildi.")

                root.after(0, basarili)
            except Exception as exc:
                def hatali():
                    log_yaz(f"[-] {exc}")
                    status_var.set("Hata oluştu")
                    messagebox.showerror("Transkript alınamadı", str(exc))

                root.after(0, hatali)
            finally:
                root.after(0, lambda: indir_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    ana = ttk.Frame(root, padding=16)
    ana.pack(fill="both", expand=True)
    ana.columnconfigure(1, weight=1)
    ana.rowconfigure(9, weight=1)

    ttk.Label(ana, text="YouTube linki").grid(row=0, column=0, sticky="w", pady=(0, 6))
    ttk.Entry(ana, textvariable=url_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 6))

    ttk.Label(ana, text="Kayıt klasörü").grid(row=1, column=0, sticky="w", pady=6)
    ttk.Entry(ana, textvariable=output_var).grid(row=1, column=1, sticky="ew", pady=6)
    ttk.Button(ana, text="Seç", command=klasor_sec).grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=6)

    ttk.Label(ana, text="Dosya adı").grid(row=2, column=0, sticky="w", pady=6)
    ttk.Entry(ana, textvariable=base_name_var).grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
    ttk.Label(ana, text="Boş bırakırsan video ID kullanılır.").grid(row=3, column=1, columnspan=2, sticky="w")

    dil_frame = ttk.LabelFrame(ana, text="İndirilecek metinler", padding=10)
    dil_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(14, 6))
    ttk.Checkbutton(dil_frame, text="Türkçe", variable=tr_var).pack(side="left", padx=(0, 18))
    ttk.Checkbutton(dil_frame, text="İngilizce", variable=en_var).pack(side="left", padx=(0, 18))
    ttk.Checkbutton(dil_frame, text="Yoksa çevirmeyi dene", variable=translate_var).pack(side="left")

    format_frame = ttk.LabelFrame(ana, text="Dosya formatı", padding=10)
    format_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=6)
    ttk.Checkbutton(format_frame, text="TXT", variable=txt_var).pack(side="left", padx=(0, 18))
    ttk.Checkbutton(format_frame, text="PDF", variable=pdf_var).pack(side="left")

    indir_button = ttk.Button(ana, text="Transkriptleri İndir", command=indir_baslat)
    indir_button.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 8))

    ttk.Label(ana, textvariable=status_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 8))
    ttk.Label(ana, text="İşlem günlüğü").grid(row=8, column=0, columnspan=3, sticky="w")

    log = scrolledtext.ScrolledText(ana, height=12, state="disabled", wrap="word")
    log.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
    log_yaz("Linki yapıştır, dil seç, indir.")

    root.mainloop()


def main():
    if len(sys.argv) == 1:
        gui_baslat()
        return

    parser = argparse.ArgumentParser(description="YouTube videolarından erişilebilir altyazı/transkript indirir.")
    parser.add_argument("url")
    parser.add_argument("-o", "--output", default="transkript.txt")
    parser.add_argument(
        "-l",
        "--languages",
        default="tr",
        help="Virgülle ayrılmış dil önceliği. İlk dil indirilir. Örnek: tr,en,de",
    )
    parser.add_argument(
        "-f",
        "--formats",
        default="txt",
        help="GUI toplu kullanım için format listesi. Örnek: txt,pdf",
    )
    args = parser.parse_args()

    languages = tuple(language.strip() for language in args.languages.split(",") if language.strip())

    try:
        formats = tuple(format.strip().lower() for format in args.formats.split(",") if format.strip())
        output_path = Path(args.output)
        if output_path.suffix:
            transkript_indir(args.url, args.output, languages)
        else:
            sonuclar, hatalar = transkriptleri_indir(args.url, output_path, languages, formats=formats)
            for sonuc in sonuclar:
                print(f"[+] {sonuc['dil']}: {sonuc['kelime']} kelime")
                for dosya in sonuc["dosyalar"]:
                    print(f"    {dosya.resolve()}")
                print(f"    Kaynak: {sonuc['kaynak']}")
            for hata in hatalar:
                print(f"[!] {hata['dil']}: {hata['hata']}")
    except TranscriptError as exc:
        print(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
