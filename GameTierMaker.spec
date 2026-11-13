# -*- mode: python ; coding: utf-8 -*-
# Облегчённая сборка: из exe выкинуто всё, чем приложение не пользуется.

EXCLUDED_MODULES = [
    # Qt-модули, которые не нужны (используются только QtCore / QtGui / QtWidgets)
    'PyQt6.QtNetwork', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtXml',
    'PyQt6.QtDBus', 'PyQt6.QtBluetooth', 'PyQt6.QtPrintSupport', 'PyQt6.QtWebSockets',
    'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
    # Pillow: редкие форматы и интеграции
    'PIL.AvifImagePlugin', 'PIL._avif', 'PIL.ImageTk', 'PIL._imagingtk', 'PIL._tkinter_finder',
    'PIL.ImageQt', 'PIL.ImageCms', 'PIL._imagingcms', 'PIL.ImageMath', 'PIL._imagingmath',
    'PIL.ImageShow', 'PIL.ImageGrab', 'PIL.ImageWin', 'PIL.ImageFont', 'PIL.ImageDraw', 'PIL._imagingft',
    # Стандартная библиотека, которая не используется
    'tkinter', '_tkinter', 'unittest', 'pydoc', 'pydoc_data', 'doctest', 'pdb', 'test', 'lib2to3',
    'sqlite3', '_sqlite3', 'curses', 'multiprocessing', 'xmlrpc', 'ftplib', 'imaplib', 'poplib',
    'smtplib', 'telnetlib', 'nntplib', 'wsgiref', 'turtle', 'idlelib', 'ensurepip', 'venv',
    'setuptools', 'pip', 'pkg_resources', 'distutils', 'numpy',
]

# Файлы Qt, которые PyInstaller кладёт «на всякий случай»
DROP_SUBSTRINGS = [
    'opengl32sw.dll', 'd3dcompiler', 'libegl', 'libgles',
    'qt6network', 'qt6svg', 'qt6pdf', 'qt6opengl', 'qt6qml', 'qt6quick', 'qt6dbus',
    '\\translations\\', '/translations/',
    '\\plugins\\tls\\', '\\plugins\\networkinformation\\', '\\plugins\\generic\\',
    '\\plugins\\iconengines\\', '\\plugins\\platforminputcontexts\\',
    'qminimal.dll', 'qoffscreen.dll', 'qdirect2d.dll',
    'qtiff.dll', 'qsvg.dll', 'qpdf.dll', 'qicns.dll', 'qtga.dll', 'qwbmp.dll',
]


def keep(entry):
    name = entry[0].lower().replace('/', '\\')
    return not any(s.replace('/', '\\') in name for s in DROP_SUBSTRINGS)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
    optimize=2,
)
a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GameTierMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
