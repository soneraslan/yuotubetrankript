# -*- mode: python ; coding: utf-8 -*-
# YouTube Transkript İndirici - PyInstaller spec dosyası

block_cipher = None

# Gereksiz büyük kütüphaneleri dışarıda bırak
EXCLUDES = [
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'keras',
    'cv2', 'opencv',
    'ultralytics',
    'numpy', 'pandas', 'scipy', 'sklearn', 'matplotlib',
    'PIL',  # reportlab kendi ihtiyacını karşılar
    'IPython', 'jupyter', 'notebook',
    'wx', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'gi', 'gtk',
    'sqlalchemy', 'django', 'flask', 'fastapi',
    'crewai', 'langchain', 'openai', 'anthropic',
    'pytest', 'unittest',
    'sphinx', 'docutils',
    'pydantic',
    'psutil',
    'multiprocessing',
    'concurrent',
]

a = Analysis(
    ['ytt.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # youtube-transcript-api
        'youtube_transcript_api',
        'youtube_transcript_api._transcripts',
        'youtube_transcript_api._errors',
        'youtube_transcript_api.formatters',
        # yt-dlp (sadece core)
        'yt_dlp',
        'yt_dlp.YoutubeDL',
        'yt_dlp.extractor.youtube',
        # reportlab
        'reportlab',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase.ttfonts',
        'reportlab.platypus',
        # requests bağımlılıkları
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        # defusedxml
        'defusedxml',
        # tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YouTubeTranskript',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI mod — konsol penceresi açılmaz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
