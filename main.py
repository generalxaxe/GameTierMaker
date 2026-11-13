import sys
import os
import re
import json
import copy
import time
import shutil
import hashlib
import ntpath
import traceback
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image, ImageOps

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QFrame, QInputDialog, QMessageBox, QLayout, QSizePolicy,
    QMenu, QSplitter, QGraphicsDropShadowEffect, QFileDialog, QWidgetItem
)
from PyQt6.QtCore import (
    Qt, QSize, QRect, QRectF, QPoint, QPointF, QMimeData, QThread,
    pyqtSignal, QTimer, QVariantAnimation, QEasingCurve, QEvent, QSettings
)
from PyQt6.QtGui import (
    QPixmap, QDrag, QFont, QIcon, QPainter, QColor, QPen, QBrush, QPainterPath,
    QPolygonF, QLinearGradient, QFontMetrics, QPalette, QShortcut, QKeySequence,
    QMouseEvent
)

# --- ПАПКИ ПРИЛОЖЕНИЯ (РАБОТАЕТ И В PYCHARM, И В .EXE) ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR


def _find_data_dir() -> str:
    override = os.environ.get("TIERMAKER_DATA_DIR")
    if override:
        return os.path.abspath(override)
    here = os.path.join(BASE_DIR, "tiermaker_data")
    if getattr(sys, 'frozen', False) and not os.path.isdir(here):
        # exe лежит в dist\ внутри проекта — берём данные проекта, а не создаём пустые
        parent = os.path.join(os.path.dirname(BASE_DIR), "tiermaker_data")
        if os.path.isdir(parent):
            return parent
    return here


DATA_DIR = _find_data_dir()
CACHE_DIR = os.path.join(DATA_DIR, "images")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
STATE_FILE = os.path.join(DATA_DIR, "workspace.json")
ERROR_LOG = os.path.join(DATA_DIR, "error.log")
UI_STATE_FILE = os.path.join(DATA_DIR, "ui_state.ini")
MAX_BACKUPS = 30

TIERS_CONFIG = [
    ("S", "#ff7f7f"),
    ("A", "#ffbf7f"),
    ("B", "#ffdf7f"),
    ("C", "#ffff7f"),
    ("D", "#bfff7f"),
    ("E", "#7fff7f"),
    ("F", "#7fffff")
]

CARD_SIZE = 90
CARD_MIME = "application/x-tiermaker-card"

# --- ПАЛИТРА ---
BG = "#0e1016"
SURFACE = "#151821"
SURFACE_2 = "#1b1f2a"
SURFACE_3 = "#232836"
BORDER = "#262b39"
BORDER_HI = "#39405a"
TEXT = "#e8ebf3"
MUTED = "#8b93a8"
ACCENT = "#7c8cff"
ACCENT_HI = "#98a5ff"
DANGER = "#ff6b6b"
SUCCESS = "#5fdc8a"

# Кеши в ОЗУ
SEARCH_MEM_CACHE = {}
THUMB_MEM_CACHE = {}

GLOBAL_SESSION = requests.Session()
GLOBAL_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
})
_adapter = requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30)
GLOBAL_SESSION.mount("https://", _adapter)
GLOBAL_SESSION.mount("http://", _adapter)


# --- БАЗА ПОПУЛЯРНЫХ ИГР ВНЕ STEAM ---
NON_STEAM_PRESETS = [
    {
        "id": "preset_minecraft",
        "name": "Minecraft",
        "source": "GLOBAL",
        "keys": ["minecraft", "майнкрафт", "майн"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/b/b6/Minecraft_2024_cover_art.png"
    },
    {
        "id": "preset_roblox",
        "name": "Roblox",
        "source": "GLOBAL",
        "keys": ["roblox", "роблокс"],
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Roblox_Logo_2022.jpg"
    },
    {
        "id": "preset_valorant",
        "name": "Valorant",
        "source": "GLOBAL",
        "keys": ["valorant", "валорант"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/b/ba/Valorant_cover.jpg"
    },
    {
        "id": "preset_lol",
        "name": "League of Legends",
        "source": "GLOBAL",
        "keys": ["league of legends", "lol", "лол", "лига легенд"],
        "img_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/League_of_Legends_2019_vector.svg/512px-League_of_Legends_2019_vector.svg.png"
    },
    {
        "id": "preset_genshin",
        "name": "Genshin Impact",
        "source": "GLOBAL",
        "keys": ["genshin", "genshin impact", "геншин"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/5/5d/Genshin_Impact_cover.jpg"
    },
    {
        "id": "preset_tarkov",
        "name": "Escape from Tarkov",
        "source": "GLOBAL",
        "keys": ["tarkov", "escape from tarkov", "тарков"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/2/26/Escape_from_Tarkov_cover.jpg"
    },
    {
        "id": "preset_fortnite",
        "name": "Fortnite",
        "source": "GLOBAL",
        "keys": ["fortnite", "фортнайт"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/7/7c/Fortnite_F_lettermark_logo.png"
    },
    {
        "id": "preset_wow",
        "name": "World of Warcraft",
        "source": "GLOBAL",
        "keys": ["world of warcraft", "wow", "вов", "варкрафт"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/6/65/World_of_Warcraft.png"
    },
    {
        "id": "preset_wc3",
        "name": "Warcraft III: The Frozen Throne",
        "source": "GLOBAL",
        "keys": ["warcraft 3", "warcraft iii", "варкрафт 3"],
        "img_url": "https://upload.wikimedia.org/wikipedia/en/5/56/Warcraft_III_The_Frozen_Throne_box_art.jpg"
    }
]

GAME_ALIASES = {
    "resident evil 8": "Resident Evil Village",
    "re 8": "Resident Evil Village",
    "re8": "Resident Evil Village",
    "резидент 8": "Resident Evil Village",
    "resident evil 9": "Resident Evil Requiem",
    "re 9": "Resident Evil Requiem",
    "re9": "Resident Evil Requiem",
    "резидент 9": "Resident Evil Requiem",
    "resident evil 7": "Resident Evil 7 Biohazard",
    "re 7": "Resident Evil 7 Biohazard",
    "re7": "Resident Evil 7 Biohazard",
    "резидент": "Resident Evil",
    "gta 5": "Grand Theft Auto V",
    "gta 4": "Grand Theft Auto IV",
    "gta sa": "Grand Theft Auto San Andreas",
    "гта 5": "Grand Theft Auto V",
    "гта": "Grand Theft Auto",
    "ведьмак 3": "The Witcher 3: Wild Hunt",
    "ведьмак": "The Witcher",
    "дота": "Dota 2",
    "дота 2": "Dota 2",
    "кс": "Counter-Strike 2",
    "кс 2": "Counter-Strike 2",
    "cs2": "Counter-Strike 2",
    "cs 2": "Counter-Strike 2",
    "скайрим": "The Elder Scrolls V: Skyrim",
    "дарк соулс": "Dark Souls",
    "элден ринг": "Elden Ring",
    "киберпанк": "Cyberpunk 2077",
    "герои 3": "Heroes of Might & Magic III",
    "homm 3": "Heroes of Might & Magic III",
    "майнкрафт": "Minecraft",
    "майн": "Minecraft",
    "роблокс": "Roblox",
    "валорант": "Valorant",
    "геншин": "Genshin Impact",
    "тарков": "Escape from Tarkov",
    "фортнайт": "Fortnite",
}


def normalize_query(raw_query: str) -> str:
    q_low = raw_query.lower().strip()
    if q_low in GAME_ALIASES:
        return GAME_ALIASES[q_low]
    for alias_k, alias_v in GAME_ALIASES.items():
        if q_low.startswith(alias_k + " "):
            return q_low.replace(alias_k, alias_v, 1)
    return raw_query.strip()


def normalize_title_for_dedup(title: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]", "", title.lower())


# ============================================================================
#  ХРАНИЛИЩЕ: загрузка / сохранение без риска потерять тир-листы
# ============================================================================
def _empty_board() -> dict:
    return {"tiers": {t[0]: [] for t in TIERS_CONFIG}, "pool": [], "games_info": {}}


def _default_workspace() -> dict:
    return {
        "folders": {"Мои Тир-листы": {"Основной тир-лист": _empty_board()}},
        "last_opened": ["Мои Тир-листы", "Основной тир-лист"]
    }


def _normalize_workspace(data: dict):
    """Дополняет недостающие поля, ничего не удаляя."""
    for boards in data["folders"].values():
        if not isinstance(boards, dict):
            continue
        for board in boards.values():
            if not isinstance(board, dict):
                continue
            if not isinstance(board.get("tiers"), dict):
                board["tiers"] = {}
            for letter, _ in TIERS_CONFIG:
                if not isinstance(board["tiers"].get(letter), list):
                    board["tiers"][letter] = []
            if not isinstance(board.get("pool"), list):
                board["pool"] = []
            if not isinstance(board.get("games_info"), dict):
                board["games_info"] = {}
    lo = data.get("last_opened")
    if not (isinstance(lo, list) and len(lo) == 2):
        data["last_opened"] = [None, None]


def _read_workspace_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("folders"), dict):
        raise ValueError("неверная структура файла")
    return data


def _list_backups() -> list:
    try:
        names = [n for n in os.listdir(BACKUP_DIR) if n.startswith("workspace_") and n.endswith(".json")]
    except OSError:
        return []
    return [os.path.join(BACKUP_DIR, n) for n in sorted(names)]


def _make_backup():
    """Копия workspace.json при запуске (если отличается от последней копии)."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        with open(STATE_FILE, "rb") as f:
            current = f.read()
        backups = _list_backups()
        if backups:
            with open(backups[-1], "rb") as f:
                if f.read() == current:
                    return
        name = time.strftime("workspace_%Y%m%d_%H%M%S.json")
        with open(os.path.join(BACKUP_DIR, name), "wb") as f:
            f.write(current)
        for old in _list_backups()[:-MAX_BACKUPS]:
            try:
                os.remove(old)
            except OSError:
                pass
    except Exception:
        pass


def load_workspace():
    """Возвращает (data, warning). Битый файл никогда не затирается — он сохраняется рядом."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    warning = None
    if os.path.exists(STATE_FILE):
        try:
            data = _read_workspace_file(STATE_FILE)
            _make_backup()
        except Exception as e:
            broken = STATE_FILE + time.strftime(".broken-%Y%m%d_%H%M%S")
            try:
                shutil.copy2(STATE_FILE, broken)
            except Exception:
                pass
            data = None
            for bpath in reversed(_list_backups()):
                try:
                    data = _read_workspace_file(bpath)
                    warning = (
                        f"Файл с тир-листами был повреждён ({e}).\n\n"
                        f"Восстановлена резервная копия:\n{os.path.basename(bpath)}\n\n"
                        f"Повреждённый файл сохранён как:\n{os.path.basename(broken)}"
                    )
                    break
                except Exception:
                    continue
            if data is None:
                data = _default_workspace()
                warning = (
                    f"Файл с тир-листами повреждён ({e}), резервных копий нет.\n\n"
                    f"Повреждённый файл сохранён как:\n{os.path.basename(broken)}"
                )
    else:
        data = _default_workspace()
    _normalize_workspace(data)
    return data, warning


def save_workspace(data: dict):
    """Атомарная запись: сначала во временный файл, потом подмена."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)


def resolve_image_path(path: str) -> str:
    """Находит картинку, даже если папку проекта переместили."""
    if not path:
        return ""
    if os.path.isfile(path):
        return path
    candidate = os.path.join(CACHE_DIR, ntpath.basename(path))
    return candidate if os.path.isfile(candidate) else ""


def make_square_cover(img_bytes_or_path, save_path: str):
    src = BytesIO(img_bytes_or_path) if isinstance(img_bytes_or_path, (bytes, bytearray)) else img_bytes_or_path
    img = Image.open(src).convert("RGBA")
    sq_img = ImageOps.fit(img, (172, 172), Image.Resampling.LANCZOS)
    tmp = save_path + ".tmp"
    sq_img.save(tmp, "PNG")
    os.replace(tmp, save_path)


def mix(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


# ============================================================================
#  ИКОНКИ
# ============================================================================
class Icons:
    @staticmethod
    def icon(kind: str, size: int = 20, color: str = TEXT) -> QIcon:
        return QIcon(Icons.pixmap(kind, size, color))

    @staticmethod
    def pixmap(kind: str, size: int = 20, color: str = TEXT) -> QPixmap:
        dpr = 2.0
        pix = QPixmap(int(size * dpr), int(size * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = QColor(color)
        round_pen = QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(round_pen)
        s = float(size)

        if kind == "folder":
            path = QPainterPath()
            path.moveTo(s * 0.12, s * 0.26)
            path.lineTo(s * 0.40, s * 0.26)
            path.lineTo(s * 0.50, s * 0.38)
            path.lineTo(s * 0.88, s * 0.38)
            path.lineTo(s * 0.88, s * 0.80)
            path.lineTo(s * 0.12, s * 0.80)
            path.closeSubpath()
            fill = QColor(c)
            fill.setAlpha(60)
            p.setBrush(fill)
            p.drawPath(path)

        elif kind == "tierlist":
            p.setPen(Qt.PenStyle.NoPen)
            colors = ["#ff7f7f", "#ffbf7f", "#ffff7f", "#7fff7f"]
            gap = s * 0.06
            row_h = (s * 0.76 - gap * 3) / 4.0
            for i, col in enumerate(colors):
                y = s * 0.12 + i * (row_h + gap)
                p.setBrush(QColor(col))
                p.drawRoundedRect(QRectF(s * 0.10, y, s * 0.24, row_h), 1.2, 1.2)
                p.setBrush(QColor("#4a5168"))
                p.drawRoundedRect(QRectF(s * 0.40, y, s * 0.50, row_h), 1.2, 1.2)

        elif kind == "plus":
            p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(s * 0.5, s * 0.22), QPointF(s * 0.5, s * 0.78))
            p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.78, s * 0.5))

        elif kind == "check":
            p.setPen(QPen(c, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.2, s * 0.52), QPointF(s * 0.42, s * 0.74), QPointF(s * 0.82, s * 0.26)
            ]))

        elif kind == "trash":
            p.drawLine(QPointF(s * 0.2, s * 0.28), QPointF(s * 0.8, s * 0.28))
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.38, s * 0.28), QPointF(s * 0.38, s * 0.16),
                QPointF(s * 0.62, s * 0.16), QPointF(s * 0.62, s * 0.28)
            ]))
            p.drawRoundedRect(QRectF(s * 0.26, s * 0.28, s * 0.48, s * 0.58), 2, 2)
            p.drawLine(QPointF(s * 0.42, s * 0.42), QPointF(s * 0.42, s * 0.72))
            p.drawLine(QPointF(s * 0.58, s * 0.42), QPointF(s * 0.58, s * 0.72))

        elif kind == "search":
            p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawEllipse(QRectF(s * 0.16, s * 0.16, s * 0.5, s * 0.5))
            p.drawLine(QPointF(s * 0.60, s * 0.60), QPointF(s * 0.84, s * 0.84))

        elif kind in ("reset", "undo"):
            p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if kind == "undo":
                p.translate(s, 0)
                p.scale(-1, 1)
            rect = QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6)
            p.drawArc(rect, 30 * 16, 270 * 16)
            p.setBrush(c)
            p.drawPolygon(QPolygonF([
                QPointF(s * 0.72, s * 0.13), QPointF(s * 0.88, s * 0.38), QPointF(s * 0.58, s * 0.38)
            ]))

        elif kind == "close":
            p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(s * 0.27, s * 0.27), QPointF(s * 0.73, s * 0.73))
            p.drawLine(QPointF(s * 0.73, s * 0.27), QPointF(s * 0.27, s * 0.73))

        elif kind == "image":
            p.drawRoundedRect(QRectF(s * 0.14, s * 0.2, s * 0.72, s * 0.6), 2.5, 2.5)
            p.drawEllipse(QRectF(s * 0.28, s * 0.32, s * 0.13, s * 0.13))
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.18, s * 0.74), QPointF(s * 0.45, s * 0.50), QPointF(s * 0.62, s * 0.65),
                QPointF(s * 0.72, s * 0.56), QPointF(s * 0.82, s * 0.70)
            ]))

        elif kind == "export":
            p.drawLine(QPointF(s * 0.5, s * 0.14), QPointF(s * 0.5, s * 0.60))
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.30, s * 0.42), QPointF(s * 0.5, s * 0.62), QPointF(s * 0.70, s * 0.42)
            ]))
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.16, s * 0.66), QPointF(s * 0.16, s * 0.84),
                QPointF(s * 0.84, s * 0.84), QPointF(s * 0.84, s * 0.66)
            ]))

        elif kind == "edit":
            p.drawPolygon(QPolygonF([
                QPointF(s * 0.20, s * 0.80), QPointF(s * 0.24, s * 0.62),
                QPointF(s * 0.66, s * 0.20), QPointF(s * 0.80, s * 0.34),
                QPointF(s * 0.38, s * 0.76)
            ]))

        elif kind == "copy":
            p.drawRoundedRect(QRectF(s * 0.34, s * 0.34, s * 0.48, s * 0.48), 2, 2)
            p.drawPolyline(QPolygonF([
                QPointF(s * 0.26, s * 0.62), QPointF(s * 0.18, s * 0.62),
                QPointF(s * 0.18, s * 0.18), QPointF(s * 0.62, s * 0.18), QPointF(s * 0.62, s * 0.26)
            ]))

        p.end()
        return pix


# ============================================================================
#  FLOW LAYOUT (перенос карточек на новую строку)
# ============================================================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=8, gap=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._gap = gap
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def insertWidget(self, index, widget):
        self.addChildWidget(widget)
        self._items.insert(max(0, min(index, len(self._items))), QWidgetItem(widget))
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def widgets(self):
        return [w for w in (it.widget() for it in self._items) if w is not None]

    def gap(self):
        return self._gap

    def expandingDirections(self):
        return Qt.Orientation(0)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        m = self.contentsMargins()
        return QSize(CARD_SIZE + m.left() + m.right(), CARD_SIZE + m.top() + m.bottom())

    def height_for_width(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def _do_layout(self, rect, apply):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and line_h > 0:
                x = area.x()
                y += line_h + self._gap
                line_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


# ============================================================================
#  ПОИСК (STEAM + VNDB + WIKIPEDIA + GOG)
# ============================================================================
class LiveSearchWorker(QThread):
    results_ready = pyqtSignal(str, list)
    thumb_ready = pyqtSignal(str, bytes)

    def __init__(self, query):
        super().__init__()
        self.query = query
        self._abort = False

    def abort(self):
        self._abort = True

    def _search_presets(self, raw_q: str, norm_q: str) -> list:
        queries = {raw_q.lower().strip(), norm_q.lower().strip()}
        out = []
        for p in NON_STEAM_PRESETS:
            hit = any(
                k.startswith(q) or q.startswith(k) or (len(q) >= 3 and q in k)
                for q in queries if q for k in p["keys"]
            )
            if hit:
                out.append({
                    "id": p["id"], "name": p["name"], "source": p["source"],
                    "img_url": p["img_url"], "fallback_url": p["img_url"], "tiny_url": p["img_url"],
                })
        return out

    def _search_steam(self, term: str) -> list:
        out = []
        resp = GLOBAL_SESSION.get(
            "https://store.steampowered.com/api/storesearch/",
            params={"term": term, "l": "english", "cc": "US"}, timeout=3.5
        )
        if resp.status_code == 200:
            for item in (resp.json().get("items") or [])[:6]:
                app_id = str(item.get("id"))
                out.append({
                    "id": f"steam_{app_id}",
                    "name": item.get("name") or "Unknown",
                    "source": "STEAM",
                    "img_url": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/library_600x900.jpg",
                    "fallback_url": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg",
                    "tiny_url": item.get("tiny_image") or "",
                })
        return out

    def _search_vndb(self, term: str) -> list:
        out = []
        payload = {
            "filters": ["search", "=", term],
            "fields": "id, title, image.url, image.thumbnail",
            "results": 6
        }
        resp = GLOBAL_SESSION.post("https://api.vndb.org/kana/vn", json=payload, timeout=3.5)
        if resp.status_code == 200:
            for item in resp.json().get("results") or []:
                img_obj = item.get("image") or {}
                full_url = img_obj.get("url") or ""
                thumb_url = img_obj.get("thumbnail") or full_url
                if not thumb_url:
                    continue
                out.append({
                    "id": f"vndb_{item.get('id')}",
                    "name": item.get("title") or "Unknown VN",
                    "source": "VNDB 18+",
                    "img_url": full_url, "fallback_url": thumb_url, "tiny_url": thumb_url,
                })
        return out

    def _search_gog(self, term: str) -> list:
        out = []
        params = {"limit": 4, "query": f"like:{term}", "productType": "in:game,pack"}
        resp = GLOBAL_SESSION.get("https://catalog.gog.com/v1/catalog", params=params, timeout=3.5)
        if resp.status_code == 200:
            for prod in resp.json().get("products") or []:
                cov = prod.get("coverHorizontal") or prod.get("coverVertical") or ""
                if not cov:
                    continue
                out.append({
                    "id": f"gog_{prod.get('id')}",
                    "name": prod.get("title") or "Unknown GOG",
                    "source": "GOG",
                    "img_url": cov, "fallback_url": cov, "tiny_url": cov,
                })
        return out

    def _search_wikipedia_games(self, term: str) -> list:
        out = []
        params = {
            "action": "query", "generator": "search", "gsrsearch": f"{term} video game",
            "gsrlimit": 4, "prop": "pageimages|description", "piprop": "thumbnail|original",
            "pithumbsize": 300, "format": "json"
        }
        resp = GLOBAL_SESSION.get("https://en.wikipedia.org/w/api.php", params=params, timeout=3.5)
        if resp.status_code == 200:
            pages = (resp.json().get("query") or {}).get("pages") or {}
            for page_id, pdata in pages.items():
                title = pdata.get("title") or ""
                clean_title = re.sub(r"\s*\(.*?video game.*?\)", "", title, flags=re.IGNORECASE).strip()
                thumb_url = (pdata.get("thumbnail") or {}).get("source") or ""
                orig_url = (pdata.get("original") or {}).get("source") or thumb_url
                if not thumb_url or not clean_title:
                    continue
                out.append({
                    "id": f"wiki_{page_id}",
                    "name": clean_title,
                    "source": "GLOBAL",
                    "img_url": orig_url, "fallback_url": thumb_url, "tiny_url": thumb_url,
                })
        return out

    def _fetch_thumb(self, game_id: str, url: str):
        if self._abort or not url:
            return
        try:
            data = THUMB_MEM_CACHE.get(game_id)
            if data is None:
                r = GLOBAL_SESSION.get(url, timeout=4.0)
                if r.status_code != 200 or len(r.content) < 200:
                    return
                data = r.content
                THUMB_MEM_CACHE[game_id] = data
            if not self._abort:
                self.thumb_ready.emit(game_id, data)
        except Exception:
            pass

    def _load_thumbs(self, games):
        with ThreadPoolExecutor(max_workers=8) as ex:
            for g in games:
                if self._abort:
                    break
                ex.submit(self._fetch_thumb, g["id"], g.get("tiny_url"))

    def run(self):
        try:
            self._run()
        except Exception:
            if not self._abort:
                self.results_ready.emit(self.query, [])

    def _run(self):
        q_key = self.query.lower().strip()
        cached = SEARCH_MEM_CACHE.get(q_key)
        if cached is not None:
            if not self._abort:
                self.results_ready.emit(self.query, cached)
                self._load_thumbs(cached)
            return

        norm_q = normalize_query(self.query)
        presets_list = self._search_presets(self.query, norm_q)
        buckets = {"STEAM": [], "VNDB": [], "WIKI": [], "GOG": []}
        any_ok = False

        with ThreadPoolExecutor(max_workers=4) as ex:
            fut_map = {
                ex.submit(self._search_steam, norm_q): "STEAM",
                ex.submit(self._search_vndb, norm_q): "VNDB",
                ex.submit(self._search_wikipedia_games, norm_q): "WIKI",
                ex.submit(self._search_gog, norm_q): "GOG"
            }
            for fut in as_completed(fut_map):
                try:
                    buckets[fut_map[fut]] = fut.result()
                    any_ok = True
                except Exception:
                    pass

        if self._abort:
            return

        combined, seen_ids, seen_titles = [], set(), set()
        ordered = [presets_list, buckets["STEAM"][:5], buckets["VNDB"][:5], buckets["WIKI"][:3], buckets["GOG"][:3]]
        for lst in ordered:
            for item in lst:
                gid = item["id"]
                norm_title = normalize_title_for_dedup(item["name"])
                dedup_key = f"vndb_{norm_title}" if item["source"] == "VNDB 18+" else norm_title
                if gid in seen_ids or (dedup_key in seen_titles and item["source"] in ("GOG", "GLOBAL")):
                    continue
                seen_ids.add(gid)
                seen_titles.add(dedup_key)
                combined.append(item)
        combined = combined[:14]

        # Пустой результат из-за отвалившейся сети не кешируем
        if combined or any_ok:
            SEARCH_MEM_CACHE[q_key] = combined
        self.results_ready.emit(self.query, combined)
        self._load_thumbs(combined)


class ImageDownloadWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, game_data, target):
        super().__init__()
        self.game_data = dict(game_data)
        self.target = target  # (папка, тир-лист), куда добавляем

    def run(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            game_id = self.game_data["id"]
            save_path = os.path.join(CACHE_DIR, f"{game_id}.png")

            if not os.path.isfile(save_path):
                candidates = []
                for url_key in ("fallback_url", "img_url", "tiny_url"):
                    url = self.game_data.get(url_key)
                    if url and url not in candidates:
                        candidates.append(url)

                saved = False
                for url in candidates:
                    try:
                        r = GLOBAL_SESSION.get(url, timeout=7)
                        if r.status_code == 200 and len(r.content) > 400:
                            make_square_cover(r.content, save_path)
                            saved = True
                            break
                    except Exception:
                        continue

                if not saved:
                    thumb = THUMB_MEM_CACHE.get(game_id)
                    if thumb:
                        try:
                            make_square_cover(thumb, save_path)
                            saved = True
                        except Exception:
                            pass
                if not saved:
                    self.failed.emit("Не удалось загрузить обложку")
                    return

            self.game_data["image_path"] = save_path
            self.done.emit(self.game_data)
        except Exception as e:
            self.failed.emit(f"Ошибка: {e}")


# ============================================================================
#  ВЫПАДАЮЩИЙ СПИСОК РЕЗУЛЬТАТОВ ПОИСКА
# ============================================================================
BADGE_COLORS = {
    "STEAM": ("#16283a", "#66c0f4"),
    "VNDB 18+": ("#3a1830", "#ff7eb6"),
    "GLOBAL": ("#16332a", "#6be695"),
    "GOG": ("#2c1d3d", "#c98bff"),
}


class SuggestionRow(QWidget):
    clicked = pyqtSignal(dict)
    ROW_H = 60
    THUMB_W, THUMB_H = 104, 46

    def __init__(self, game_data, is_added=False):
        super().__init__()
        self.game_data = game_data
        self.is_added = is_added
        self._hover = False
        self._selected = False
        self._thumb = None
        self.setFixedHeight(self.ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        thumb = THUMB_MEM_CACHE.get(game_data["id"])
        if thumb:
            self.set_thumbnail(thumb)

    def set_thumbnail(self, img_bytes: bytes):
        pix = QPixmap()
        if pix.loadFromData(img_bytes) and not pix.isNull():
            dpr = self.devicePixelRatioF()
            target = QSize(int(self.THUMB_W * dpr), int(self.THUMB_H * dpr))
            scaled = pix.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width() - target.width()) // 2
            y = (scaled.height() - target.height()) // 2
            self._thumb = scaled.copy(x, y, target.width(), target.height())
            self._thumb.setDevicePixelRatio(dpr)
            self.update()

    def set_selected(self, on: bool):
        if self._selected != on:
            self._selected = on
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.game_data)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        active = self._hover or self._selected

        if active:
            p.setPen(QPen(QColor(ACCENT), 1.2) if self._selected else QPen(QColor(BORDER_HI), 1))
            p.setBrush(QColor(SURFACE_3))
            p.drawRoundedRect(r, 9, 9)

        # Миниатюра
        tr = QRectF(r.left() + 8, r.center().y() - self.THUMB_H / 2, self.THUMB_W, self.THUMB_H)
        clip = QPainterPath()
        clip.addRoundedRect(tr, 6, 6)
        p.save()
        p.setClipPath(clip)
        p.fillRect(tr, QColor("#0b0d12"))
        if self._thumb:
            p.drawPixmap(tr.topLeft(), self._thumb)
        else:
            ico = Icons.pixmap("image", 18, "#3d4458")
            p.drawPixmap(QPointF(tr.center().x() - 9, tr.center().y() - 9), ico)
        p.restore()

        # Иконка статуса справа
        ico_kind, ico_col = ("check", SUCCESS) if self.is_added else ("plus", ACCENT_HI if active else MUTED)
        ico = Icons.pixmap(ico_kind, 18, ico_col)
        ico_x = r.right() - 30
        p.drawPixmap(QPointF(ico_x, r.center().y() - 9), ico)

        # Бейдж источника
        source = self.game_data.get("source", "GAME")
        bg_c, txt_c = BADGE_COLORS.get(source, (SURFACE_3, MUTED))
        bf = QFont("Segoe UI", 8, QFont.Weight.Bold)
        p.setFont(bf)
        bw = QFontMetrics(bf).horizontalAdvance(source) + 16
        br = QRectF(ico_x - 12 - bw, r.center().y() - 10, bw, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg_c))
        p.drawRoundedRect(br, 10, 10)
        p.setPen(QColor(txt_c))
        p.drawText(br, Qt.AlignmentFlag.AlignCenter, source)

        # Название
        tf = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        p.setFont(tf)
        text_rect = QRectF(tr.right() + 12, r.top(), br.left() - tr.right() - 22, r.height())
        fm = QFontMetrics(tf)
        if self.is_added:
            p.setPen(QColor(SUCCESS))
            sub_h = 16
            name_rect = QRectF(text_rect.left(), text_rect.center().y() - 17, text_rect.width(), 20)
            p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(self.game_data["name"], Qt.TextElideMode.ElideRight, int(text_rect.width())))
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(text_rect.left(), name_rect.bottom(), text_rect.width(), sub_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "уже в этом тир-листе")
        else:
            p.setPen(QColor(TEXT))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(self.game_data["name"], Qt.TextElideMode.ElideRight, int(text_rect.width())))
        p.end()


class SuggestionsPopup(QFrame):
    """Выпадающий список — дочерний виджет окна (не отдельное окно)."""
    game_selected = pyqtSignal(dict)
    SHADOW = 16

    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []
        self.rows_by_id = {}
        self._sel = -1
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.SHADOW, self.SHADOW, self.SHADOW, self.SHADOW)

        self.container = QFrame()
        self.container.setObjectName("popupContainer")
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 200))
        self.container.setGraphicsEffect(shadow)

        cl = QVBoxLayout(self.container)
        cl.setContentsMargins(6, 6, 6, 6)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)

        self.list_widget = QWidget()
        self.list_widget.setAutoFillBackground(False)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.scroll.setWidget(self.list_widget)

        cl.addWidget(self.scroll)
        outer.addWidget(self.container)

    def show_results(self, results, added_ids, anchor: QWidget):
        self.rows.clear()
        self.rows_by_id.clear()
        self._sel = -1
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

        if not results:
            self.hide()
            return

        for game in results:
            row = SuggestionRow(game, is_added=(game["id"] in added_ids))
            row.clicked.connect(self._on_row_clicked)
            self.list_layout.addWidget(row)
            self.rows.append(row)
            self.rows_by_id[game["id"]] = row
        self.list_layout.addStretch()

        self.reposition(anchor)
        self.scroll.verticalScrollBar().setValue(0)
        self.show()
        self.raise_()

    def reposition(self, anchor: QWidget):
        parent = self.parentWidget()
        if not anchor or not parent or not self.rows:
            return
        top_left = anchor.mapTo(parent, QPoint(0, anchor.height() + 6))
        avail = parent.height() - top_left.y() - 12
        max_rows = max(2, min(7, (avail - 12) // SuggestionRow.ROW_H))
        h = min(len(self.rows), max_rows) * SuggestionRow.ROW_H + 12
        self.setGeometry(
            top_left.x() - self.SHADOW, top_left.y() - self.SHADOW,
            anchor.width() + self.SHADOW * 2, h + self.SHADOW * 2
        )

    def update_thumbnail(self, game_id: str, img_bytes: bytes):
        row = self.rows_by_id.get(game_id)
        if row:
            row.set_thumbnail(img_bytes)

    def move_selection(self, delta: int):
        if not self.rows:
            return
        if self._sel < 0:
            self._sel = 0 if delta > 0 else len(self.rows) - 1
        else:
            self._sel = (self._sel + delta) % len(self.rows)
        for i, row in enumerate(self.rows):
            row.set_selected(i == self._sel)
        self.scroll.ensureWidgetVisible(self.rows[self._sel], 0, 4)

    def activate_selected(self) -> bool:
        if not self.rows:
            return False
        row = self.rows[self._sel if self._sel >= 0 else 0]
        self._on_row_clicked(row.game_data)
        return True

    def _on_row_clicked(self, game_data):
        self.hide()
        self.game_selected.emit(game_data)


# ============================================================================
#  КАРТОЧКА ИГРЫ
# ============================================================================
class GameCard(QWidget):
    removed = pyqtSignal(str)
    move_requested = pyqtSignal(str, str)

    def __init__(self, game_id, name, image_path, parent=None):
        super().__init__(parent)
        self.game_id = game_id
        self.game_name = name or game_id
        self.drag_start_pos = None
        self._scale = 1.0
        self._hover = 0.0
        self._dragging = False
        self.raw_pixmap = None

        self.setFixedSize(CARD_SIZE, CARD_SIZE)
        self.setToolTip(self.game_name)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        real_path = resolve_image_path(image_path)
        if real_path:
            pix = QPixmap(real_path)
            if not pix.isNull():
                self.raw_pixmap = pix

        self.scale_anim = QVariantAnimation(self)
        self.scale_anim.setDuration(200)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.scale_anim.valueChanged.connect(self._on_scale_changed)

        self.hover_anim = QVariantAnimation(self)
        self.hover_anim.setDuration(120)
        self.hover_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.hover_anim.valueChanged.connect(self._on_hover_changed)

    def sizeHint(self):
        return QSize(CARD_SIZE, CARD_SIZE)

    def play_pop_in(self):
        self.scale_anim.stop()
        self.scale_anim.setStartValue(0.6)
        self.scale_anim.setEndValue(1.0)
        self.scale_anim.start()

    def _on_scale_changed(self, val):
        self._scale = float(val)
        self.update()

    def _on_hover_changed(self, val):
        self._hover = float(val)
        self.update()

    def _animate_hover(self, target):
        self.hover_anim.stop()
        self.hover_anim.setStartValue(self._hover)
        self.hover_anim.setEndValue(target)
        self.hover_anim.start()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _card_rect(self) -> QRectF:
        inset = 2.5 - 2.0 * self._hover
        r = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        if self._scale != 1.0:
            c = r.center()
            w, h = r.width() * self._scale, r.height() * self._scale
            r = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        return r

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._dragging:
            p.setOpacity(0.25)

        r = self._card_rect()
        radius = 9.0
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        p.setClipPath(path)

        if self.raw_pixmap:
            p.drawPixmap(r, self.raw_pixmap, QRectF(self.raw_pixmap.rect()))
        else:
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0, QColor("#2b3147"))
            grad.setColorAt(1, QColor("#1a1e2b"))
            p.fillRect(r, grad)
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            p.drawText(r.adjusted(6, 6, -6, -6),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.game_name)

        if self._hover > 0.02 and self.raw_pixmap:
            band_h = 34.0
            band = QRectF(r.left(), r.bottom() - band_h, r.width(), band_h)
            grad = QLinearGradient(band.topLeft(), band.bottomLeft())
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(0.55, QColor(0, 0, 0, int(190 * self._hover)))
            grad.setColorAt(1, QColor(0, 0, 0, int(235 * self._hover)))
            p.fillRect(band, grad)
            f = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, int(255 * self._hover)))
            text = QFontMetrics(f).elidedText(self.game_name, Qt.TextElideMode.ElideRight, int(r.width() - 10))
            p.drawText(band.adjusted(5, 0, -5, -4),
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, text)

        p.setClipping(False)
        border = mix(QColor(0, 0, 0, 150), QColor(ACCENT_HI), self._hover)
        p.setPen(QPen(border, 1.0 + 1.0 * self._hover))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, radius, radius)
        p.end()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        zone = self.parentWidget()
        current_zone = zone.zone_id if isinstance(zone, TierDropZone) else None
        move_actions = {}
        for letter, color in TIERS_CONFIG:
            if letter == current_zone:
                continue
            sw = QPixmap(14, 14)
            sw.fill(Qt.GlobalColor.transparent)
            sp = QPainter(sw)
            sp.setRenderHint(QPainter.RenderHint.Antialiasing)
            sp.setPen(Qt.PenStyle.NoPen)
            sp.setBrush(QColor(color))
            sp.drawRoundedRect(QRectF(1, 1, 12, 12), 3, 3)
            sp.end()
            move_actions[menu.addAction(QIcon(sw), f"В тир {letter}")] = letter
        if current_zone != "POOL":
            move_actions[menu.addAction(Icons.icon("reset", 16, MUTED), "Убрать из тира (вниз)")] = "POOL"
        menu.addSeparator()
        del_act = menu.addAction(Icons.icon("trash", 16, DANGER), "Удалить из тир-листа")

        act = menu.exec(event.globalPos())
        if act is None:
            return
        if act == del_act:
            self.removed.emit(self.game_id)
        elif act in move_actions:
            self.move_requested.emit(self.game_id, move_actions[act])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self.drag_start_pos is None:
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self.drag_start_pos = None

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(CARD_MIME, self.game_id.encode("utf-8"))
        drag.setMimeData(mime)

        self._hover = 0.0
        ghost = QPixmap(self.size() * self.devicePixelRatioF())
        ghost.setDevicePixelRatio(self.devicePixelRatioF())
        ghost.fill(Qt.GlobalColor.transparent)
        self.render(ghost, QPoint(), flags=QWidget.RenderFlag.DrawChildren)
        drag.setPixmap(ghost)
        drag.setHotSpot(event.pos())

        self._dragging = True
        self.update()
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()


# ============================================================================
#  ЗОНА СБРОСА КАРТОЧЕК
# ============================================================================
class TierDropZone(QWidget):
    about_to_change = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, zone_id, main_window, base_height, placeholder=""):
        super().__init__()
        self.zone_id = zone_id
        self.main_window = main_window
        self.placeholder = placeholder
        self._base_h = base_height
        self._highlight = False
        self._indicator = None
        self.setAcceptDrops(True)
        self.setMinimumHeight(base_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.flow = FlowLayout(self, margin=8, gap=6)

    # --- размер под содержимое ---
    def refit(self):
        need = self.flow.height_for_width(max(self.width(), CARD_SIZE + 16))
        h = max(self._base_h, need)
        if h != self.minimumHeight():
            self.setMinimumHeight(h)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.refit()

    # --- карточки ---
    def cards(self):
        return [w for w in self.flow.widgets() if isinstance(w, GameCard)]

    def get_game_ids(self):
        return [c.game_id for c in self.cards()]

    def add_card(self, card: GameCard, index=-1, animate=False):
        if index < 0 or index >= self.flow.count():
            self.flow.addWidget(card)
        else:
            self.flow.insertWidget(index, card)
        card.show()
        if animate:
            card.play_pop_in()
        self.refit()

    def take_card(self, card: GameCard):
        self.flow.removeWidget(card)
        self.refit()

    def clear_cards(self):
        for card in self.cards():
            self.flow.removeWidget(card)
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self.refit()

    # --- позиция вставки ---
    def _drop_target(self, pos: QPoint, skip):
        """Возвращает (индекс вставки, прямоугольник индикатора)."""
        items = [c for c in self.cards() if c is not skip]
        gap = self.flow.gap()
        if not items:
            m = self.flow.contentsMargins()
            return 0, QRectF(m.left() - 1, m.top(), 3, CARD_SIZE)

        idx = len(items)
        for i, w in enumerate(items):
            g = w.geometry()
            if pos.y() < g.top() or (pos.y() <= g.bottom() + gap and pos.x() < g.center().x()):
                idx = i
                break

        if idx < len(items) and pos.y() >= items[idx].geometry().top() - gap:
            g = items[idx].geometry()
            x = g.left() - gap / 2.0 - 1.5
        else:
            g = items[max(0, idx - 1)].geometry()
            x = g.right() + gap / 2.0 - 0.5 if idx > 0 else g.left() - gap / 2.0 - 1.5
        return idx, QRectF(x, g.top() + 4, 3, g.height() - 8)

    def _dragged_card(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(CARD_MIME):
            return None
        gid = bytes(mime.data(CARD_MIME)).decode("utf-8", "ignore")
        return self.main_window.find_card_widget(gid)

    def _set_drag_state(self, highlight, indicator=None):
        if highlight != self._highlight or indicator != self._indicator:
            self._highlight = highlight
            self._indicator = indicator
            self.update()

    def dragEnterEvent(self, event):
        if self._dragged_card(event):
            event.acceptProposedAction()
            self._set_drag_state(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        card = self._dragged_card(event)
        if not card:
            event.ignore()
            return
        _, rect = self._drop_target(event.position().toPoint(), card)
        self._set_drag_state(True, rect)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_drag_state(False)

    def dropEvent(self, event):
        card = self._dragged_card(event)
        self._set_drag_state(False)
        if not card:
            event.ignore()
            return

        insert_idx, _ = self._drop_target(event.position().toPoint(), card)
        self.about_to_change.emit()

        old_zone = card.parentWidget()
        same_zone = old_zone is self
        if isinstance(old_zone, TierDropZone):
            old_zone.take_card(card)

        self.add_card(card, insert_idx, animate=not same_zone)
        event.acceptProposedAction()
        self.changed.emit()

    def paintEvent(self, event):
        if not (self._highlight or self._indicator or (self.placeholder and self.flow.count() == 0)):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._highlight:
            col = QColor(ACCENT)
            col.setAlpha(26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(3, 3, -3, -3), 8, 8)
        if self._indicator:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT_HI))
            p.drawRoundedRect(self._indicator, 1.5, 1.5)
        if self.placeholder and self.flow.count() == 0:
            p.setPen(QColor("#5b6378"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect().adjusted(16, 8, -16, -8),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.placeholder)
        p.end()


# ============================================================================
#  СТРОКА ТИРА
# ============================================================================
class TierLabel(QWidget):
    WIDTH = 96

    def __init__(self, letter, color, base_height):
        super().__init__()
        self.letter = letter
        self.color = QColor(color)
        self.count = 0
        self._base_h = base_height
        self.setFixedWidth(self.WIDTH)
        self.setMinimumHeight(base_height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    def sizeHint(self):
        return QSize(self.WIDTH, self._base_h)

    def set_count(self, n):
        if n != self.count:
            self.count = n
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        rad = 11.0

        path = QPainterPath()
        path.moveTo(r.right(), r.top())
        path.lineTo(r.left() + rad, r.top())
        path.quadTo(r.left(), r.top(), r.left(), r.top() + rad)
        path.lineTo(r.left(), r.bottom() - rad)
        path.quadTo(r.left(), r.bottom(), r.left() + rad, r.bottom())
        path.lineTo(r.right(), r.bottom())
        path.closeSubpath()

        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, self.color.lighter(108))
        grad.setColorAt(1, self.color.darker(112))
        p.fillPath(path, grad)

        p.setPen(QColor(20, 22, 28))
        p.setFont(QFont("Segoe UI", 26, QFont.Weight.Black))
        p.drawText(r.adjusted(0, -6, 0, -6), Qt.AlignmentFlag.AlignCenter, self.letter)

        p.setPen(QColor(20, 22, 28, 150))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(r.left(), r.center().y() + 20, r.width(), 16),
                   Qt.AlignmentFlag.AlignCenter, str(self.count))
        p.end()


class TierRowWidget(QWidget):
    BASE_H = CARD_SIZE + 16

    def __init__(self, letter, color, main_window):
        super().__init__()
        self.letter = letter
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.label = TierLabel(letter, color, self.BASE_H)
        self.drop_zone = TierDropZone(letter, main_window, self.BASE_H)
        layout.addWidget(self.label)
        layout.addWidget(self.drop_zone, 1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(SURFACE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        p.end()


# ============================================================================
#  СТИЛИ
# ============================================================================
STYLESHEET = f"""
QMainWindow, QDialog {{ background-color: {BG}; }}
QWidget {{ color: {TEXT}; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }}
QLabel {{ background: transparent; }}
QToolTip {{
    background-color: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER_HI};
    padding: 5px 8px; border-radius: 6px;
}}
QFrame#sidebar {{ background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#poolPanel {{ background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#popupContainer {{ background-color: {SURFACE_2}; border: 1px solid {BORDER_HI}; border-radius: 12px; }}
QFrame#searchBox {{ background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#searchBox[focused="true"] {{ border: 1px solid {ACCENT}; background-color: {SURFACE_2}; }}
QLineEdit#searchInput {{ background: transparent; border: none; padding: 0px; font-size: 14px; color: {TEXT}; }}
QLabel#appTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#sectionLabel {{ color: {MUTED}; font-size: 11px; font-weight: 700; }}
QLabel#boardTitle {{ font-size: 22px; font-weight: 700; }}
QLabel#boardFolder {{ color: {MUTED}; font-size: 11px; font-weight: 700; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}

QPushButton {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER}; padding: 7px 13px;
    border-radius: 9px; color: {TEXT}; font-weight: 600;
}}
QPushButton:hover {{ background-color: {SURFACE_3}; border-color: {BORDER_HI}; }}
QPushButton:pressed {{ background-color: {SURFACE}; }}
QPushButton:disabled {{ color: #565d70; background-color: {SURFACE}; border-color: {BORDER}; }}
QPushButton::menu-indicator {{ image: none; width: 0px; }}
QPushButton[kind="primary"] {{ background-color: {ACCENT}; border: 1px solid {ACCENT}; color: #0d0f17; }}
QPushButton[kind="primary"]:hover {{ background-color: {ACCENT_HI}; border-color: {ACCENT_HI}; }}
QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid transparent; padding: 5px; }}
QPushButton[kind="ghost"]:hover {{ background-color: {SURFACE_3}; }}

QLineEdit {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER}; padding: 7px 10px;
    border-radius: 8px; color: {TEXT}; selection-background-color: {ACCENT}; selection-color: #0d0f17;
}}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER}; padding: 6px 10px; border-radius: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_HI}; selection-background-color: {SURFACE_3};
}}

QTreeWidget {{
    background: transparent; border: none; outline: none; font-size: 13px;
    show-decoration-selected: 0; selection-background-color: transparent;
}}
QTreeWidget::branch, QTreeWidget::branch:selected, QTreeWidget::branch:hover {{ background: {SURFACE}; }}
QTreeWidget::item {{ padding: 8px 6px; border-radius: 8px; margin: 1px 0px; }}
QTreeWidget::item:hover {{ background-color: {SURFACE_2}; }}
QTreeWidget::item:selected {{ background-color: #2a3050; color: #ffffff; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2f3547; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:horizontal {{ background: #2f3547; border-radius: 3px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: #454d68; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{
    background-color: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER_HI};
    padding: 6px; border-radius: 10px;
}}
QMenu::item {{ padding: 7px 18px 7px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {SURFACE_3}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QSplitter::handle {{ background: transparent; }}
QMessageBox QLabel {{ font-size: 13px; }}
"""


def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_2))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(SURFACE_2))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_3))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#0d0f17"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666e84"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


# ============================================================================
#  ГЛАВНОЕ ОКНО
# ============================================================================
class TierMakerApp(QMainWindow):
    UNDO_LIMIT = 50

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game TierMaker Pro")
        icon_file = next(
            (p for p in (os.path.join(BASE_DIR, "icon.ico"), os.path.join(RESOURCE_DIR, "icon.ico"))
             if os.path.exists(p)), None
        )
        self.setWindowIcon(QIcon(icon_file) if icon_file else Icons.icon("tierlist", 32))
        self.resize(1400, 900)
        self.setMinimumSize(900, 600)

        self.workspace_data, load_warning = load_workspace()
        self.current_folder = None
        self.current_list = None
        self.card_widgets = {}
        self.undo_stack = []
        self._board_ready = False
        self._closing = False
        self.live_search_worker = None
        self._threads = set()

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.start_live_search)

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(lambda: self.lbl_search_status.setText(""))

        self.init_ui()
        self.suggestions_popup = SuggestionsPopup(self)
        self.suggestions_popup.game_selected.connect(self.on_suggestion_clicked)

        self._init_shortcuts()
        self._restore_ui_state()
        self.populate_tree()
        QApplication.instance().installEventFilter(self)

        if not os.path.exists(STATE_FILE):
            self.save_workspace_data()
        if load_warning:
            QTimer.singleShot(200, lambda: QMessageBox.warning(self, "Восстановление данных", load_warning))

    # ------------------------------------------------------------------ события
    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if obj is self.search_input and not self.suggestions_popup.isVisible():
                if len(self.search_input.text().strip()) >= 2:
                    QTimer.singleShot(0, self.start_live_search)
            elif self.suggestions_popup.isVisible():
                gp = event.globalPosition().toPoint()
                popup_rect = QRect(self.suggestions_popup.mapToGlobal(QPoint(0, 0)), self.suggestions_popup.size())
                box_rect = QRect(self.search_box.mapToGlobal(QPoint(0, 0)), self.search_box.size())
                if not popup_rect.contains(gp) and not box_rect.contains(gp):
                    self.suggestions_popup.hide()
        elif obj is self.search_input:
            if et == QEvent.Type.KeyPress:
                key = event.key()
                popup = self.suggestions_popup
                if key == Qt.Key.Key_Down and popup.isVisible():
                    popup.move_selection(1)
                    return True
                if key == Qt.Key.Key_Up and popup.isVisible():
                    popup.move_selection(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if popup.isVisible():
                        popup.activate_selected()
                    elif len(self.search_input.text().strip()) >= 2:
                        self.start_live_search()
                    return True
                if key == Qt.Key.Key_Escape:
                    if popup.isVisible():
                        popup.hide()
                    else:
                        self.search_input.clear()
                    return True
            elif et in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
                self.search_box.setProperty("focused", et == QEvent.Type.FocusIn)
                self.search_box.style().unpolish(self.search_box)
                self.search_box.style().polish(self.search_box)
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.suggestions_popup.isVisible():
            self.suggestions_popup.reposition(self.search_box)

    def closeEvent(self, event):
        self._closing = True
        try:
            if self._board_ready:
                self.sync_current_board_to_data()
            self._save_ui_state()
        except Exception:
            pass
        self.search_timer.stop()
        for t in list(self._threads):
            if isinstance(t, LiveSearchWorker):
                t.abort()
        self.hide()
        deadline = time.time() + 9.0
        for t in list(self._threads):
            t.wait(max(1, int((deadline - time.time()) * 1000)))
        super().closeEvent(event)

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_png)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_board_image)
        for key, slot in (("Delete", self.delete_selected_tree_item), ("F2", self.rename_selected_tree_item)):
            sc = QShortcut(QKeySequence(key), self.tree, activated=slot)
            sc.setContext(Qt.ShortcutContext.WidgetShortcut)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _restore_ui_state(self):
        try:
            s = QSettings(UI_STATE_FILE, QSettings.Format.IniFormat)
            geo = s.value("geometry")
            if geo is not None:
                self.restoreGeometry(geo)
            for name, splitter in (("splitter_h", self.splitter_h), ("splitter_v", self.splitter_v)):
                st = s.value(name)
                if st is not None:
                    splitter.restoreState(st)
        except Exception:
            pass

    def _save_ui_state(self):
        s = QSettings(UI_STATE_FILE, QSettings.Format.IniFormat)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter_h", self.splitter_h.saveState())
        s.setValue("splitter_v", self.splitter_v.saveState())
        s.sync()

    # ------------------------------------------------------------------ данные
    def save_workspace_data(self):
        try:
            save_workspace(self.workspace_data)
        except Exception as e:
            self.set_status(f"Не удалось сохранить: {e}", error=True, timeout=0)

    def current_board(self):
        if not self.current_folder or not self.current_list:
            return None
        return self.workspace_data["folders"].get(self.current_folder, {}).get(self.current_list)

    def sync_current_board_to_data(self):
        """Записывает расположение карточек в данные. Работает только с полностью загруженной доской."""
        board = self.current_board()
        if board is None or not self._board_ready:
            return
        for letter, row in self.tier_rows.items():
            board["tiers"][letter] = row.drop_zone.get_game_ids()
        board["pool"] = self.pool_zone.get_game_ids()
        self.save_workspace_data()
        self._update_counts()

    def push_undo(self):
        board = self.current_board()
        if board is None:
            return
        snap = copy.deepcopy({k: board[k] for k in ("tiers", "pool", "games_info")})
        self.undo_stack.append(snap)
        del self.undo_stack[:-self.UNDO_LIMIT]
        self.btn_undo.setEnabled(True)

    def undo(self):
        board = self.current_board()
        if board is None or not self.undo_stack:
            return
        board.update(self.undo_stack.pop())
        self.btn_undo.setEnabled(bool(self.undo_stack))
        self._render_board()
        self.save_workspace_data()
        self.set_status("Действие отменено")

    def set_status(self, text, error=False, timeout=4000):
        self.lbl_search_status.setStyleSheet(f"color: {DANGER if error else MUTED}; font-size: 12px;")
        self.lbl_search_status.setText(text)
        self.status_timer.stop()
        if timeout:
            self.status_timer.start(timeout)

    # ------------------------------------------------------------------ интерфейс
    def _btn(self, text="", icon=None, icon_color=TEXT, kind=None, tip="", slot=None):
        b = QPushButton((" " + text) if (text and icon) else text)
        if icon:
            b.setIcon(Icons.icon(icon, 18, icon_color))
            b.setIconSize(QSize(18, 18))
        if kind:
            b.setProperty("kind", kind)
        if tip:
            b.setToolTip(tip)
        if slot:
            b.clicked.connect(slot)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return b

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)

        self.splitter_h = QSplitter(Qt.Orientation.Horizontal)
        self.splitter_h.setHandleWidth(14)
        self.splitter_h.setChildrenCollapsible(False)
        root.addWidget(self.splitter_h)

        # ---------- ЛЕВАЯ ПАНЕЛЬ ----------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(230)
        sidebar.setMaximumWidth(380)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 16, 14, 14)
        sl.setSpacing(10)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(Icons.pixmap("tierlist", 28))
        title = QLabel("Game TierMaker")
        title.setObjectName("appTitle")
        brand.addWidget(logo)
        brand.addWidget(title)
        brand.addStretch()
        sl.addLayout(brand)
        sl.addSpacing(6)

        section = QHBoxLayout()
        lbl = QLabel("ТИР-ЛИСТЫ")
        lbl.setObjectName("sectionLabel")
        section.addWidget(lbl)
        section.addStretch()
        section.addWidget(self._btn(icon="folder", icon_color=MUTED, kind="ghost",
                                    tip="Новая папка", slot=self.create_folder))
        sl.addLayout(section)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        tree_pal = self.tree.palette()
        tree_pal.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        self.tree.setPalette(tree_pal)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.tree.currentItemChanged.connect(self.on_tree_current_changed)
        sl.addWidget(self.tree, 1)

        sl.addWidget(self._btn("  Новый тир-лист", icon="plus", icon_color="#0d0f17", kind="primary",
                               slot=self.create_tier_list))
        self.splitter_h.addWidget(sidebar)

        # ---------- ПРАВАЯ ПАНЕЛЬ ----------
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 2, 0, 0)
        rl.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.lbl_folder = QLabel("")
        self.lbl_folder.setObjectName("boardFolder")
        self.lbl_current_title = QLabel("Тир-лист не выбран")
        self.lbl_current_title.setObjectName("boardTitle")
        titles.addWidget(self.lbl_folder)
        titles.addWidget(self.lbl_current_title)
        header.addLayout(titles, 1)

        self.btn_undo = self._btn("Отменить", icon="undo", tip="Отменить последнее действие (Ctrl+Z)", slot=self.undo)
        self.btn_undo.setEnabled(False)
        self.btn_custom = self._btn("Своя картинка", icon="image", icon_color=ACCENT_HI,
                                    tip="Добавить игру со своей обложкой с компьютера",
                                    slot=self.add_custom_game_from_pc)
        self.btn_reset = self._btn("Сбросить вниз", icon="reset",
                                   tip="Вернуть все игры из тиров в нижнюю панель", slot=self.return_all_to_pool)
        self.btn_export = self._btn("Экспорт", icon="export", tip="Сохранить тир-лист картинкой")
        export_menu = QMenu(self.btn_export)
        export_menu.addAction(Icons.icon("export", 16), "Сохранить как PNG…\tCtrl+E", self.export_png)
        export_menu.addAction(Icons.icon("copy", 16), "Скопировать в буфер\tCtrl+Shift+C", self.copy_board_image)
        self.btn_export.setMenu(export_menu)
        for b in (self.btn_undo, self.btn_custom, self.btn_reset, self.btn_export):
            header.addWidget(b, 0, Qt.AlignmentFlag.AlignBottom)
        rl.addLayout(header)

        # Поиск
        self.search_box = QFrame()
        self.search_box.setObjectName("searchBox")
        self.search_box.setFixedHeight(48)
        sb = QHBoxLayout(self.search_box)
        sb.setContentsMargins(14, 0, 8, 0)
        sb.setSpacing(10)
        search_icon = QLabel()
        search_icon.setPixmap(Icons.pixmap("search", 18, MUTED))
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Найти и добавить игру — Steam, VNDB, GOG, Wikipedia…   (Ctrl+F)")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.lbl_search_status = QLabel("")
        self.lbl_search_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.btn_clear_search = self._btn(icon="close", icon_color=MUTED, kind="ghost",
                                          tip="Очистить поиск", slot=self.clear_live_search)
        self.btn_clear_search.setFixedSize(30, 30)
        self.btn_clear_search.hide()
        sb.addWidget(search_icon)
        sb.addWidget(self.search_input, 1)
        sb.addWidget(self.lbl_search_status)
        sb.addWidget(self.btn_clear_search)
        rl.addWidget(self.search_box)

        # Доска + пул в вертикальном сплиттере
        self.splitter_v = QSplitter(Qt.Orientation.Vertical)
        self.splitter_v.setHandleWidth(12)
        self.splitter_v.setChildrenCollapsible(False)

        self.tiers_scroll = QScrollArea()
        self.tiers_scroll.setWidgetResizable(True)
        self.tiers_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tiers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tiers_scroll.viewport().setAutoFillBackground(False)

        tiers_outer = QWidget()
        tiers_outer.setAutoFillBackground(False)
        tol = QVBoxLayout(tiers_outer)
        tol.setContentsMargins(0, 0, 6, 0)
        tol.setSpacing(0)

        self.board_frame = QWidget()
        bl = QVBoxLayout(self.board_frame)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        self.tier_rows = {}
        for letter, color in TIERS_CONFIG:
            row = TierRowWidget(letter, color, self)
            row.drop_zone.about_to_change.connect(self.push_undo)
            row.drop_zone.changed.connect(self.sync_current_board_to_data)
            bl.addWidget(row)
            self.tier_rows[letter] = row

        tol.addWidget(self.board_frame)
        tol.addStretch(1)
        self.tiers_scroll.setWidget(tiers_outer)
        self.splitter_v.addWidget(self.tiers_scroll)

        pool_panel = QFrame()
        pool_panel.setObjectName("poolPanel")
        pool_panel.setMinimumHeight(150)
        pl = QVBoxLayout(pool_panel)
        pl.setContentsMargins(6, 10, 6, 6)
        pl.setSpacing(2)
        pool_header = QHBoxLayout()
        pool_header.setContentsMargins(10, 0, 10, 0)
        self.lbl_pool = QLabel("БЕЗ ТИРА")
        self.lbl_pool.setObjectName("sectionLabel")
        hint = QLabel("перетаскивай карточки в тиры  •  ПКМ по карточке — меню")
        hint.setObjectName("hint")
        pool_header.addWidget(self.lbl_pool)
        pool_header.addStretch()
        pool_header.addWidget(hint)
        pl.addLayout(pool_header)

        self.pool_scroll = QScrollArea()
        self.pool_scroll.setWidgetResizable(True)
        self.pool_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.pool_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pool_scroll.viewport().setAutoFillBackground(False)
        self.pool_zone = TierDropZone(
            "POOL", self, CARD_SIZE + 16,
            placeholder="Здесь появятся добавленные игры — найди игру через поиск сверху"
        )
        self.pool_zone.setAutoFillBackground(False)
        self.pool_zone.about_to_change.connect(self.push_undo)
        self.pool_zone.changed.connect(self.sync_current_board_to_data)
        self.pool_scroll.setWidget(self.pool_zone)
        pl.addWidget(self.pool_scroll, 1)
        self.splitter_v.addWidget(pool_panel)

        self.splitter_v.setStretchFactor(0, 1)
        self.splitter_v.setStretchFactor(1, 0)
        self.splitter_v.setSizes([640, 170])
        rl.addWidget(self.splitter_v, 1)

        self.splitter_h.addWidget(right)
        self.splitter_h.setStretchFactor(0, 0)
        self.splitter_h.setStretchFactor(1, 1)
        self.splitter_h.setSizes([270, 1100])

    def _update_counts(self):
        total = 0
        for row in self.tier_rows.values():
            n = row.drop_zone.flow.count()
            row.label.set_count(n)
            total += n
        pool_n = self.pool_zone.flow.count()
        self.lbl_pool.setText(f"БЕЗ ТИРА  ·  {pool_n}" if pool_n else "БЕЗ ТИРА")
        if self.current_board() is not None:
            self.lbl_folder.setText(f"{self.current_folder.upper()}  ·  ИГР: {total + pool_n}")

    def _set_board_enabled(self, on: bool):
        for w in (self.btn_custom, self.btn_reset, self.btn_export, self.splitter_v):
            w.setEnabled(on)

    # ------------------------------------------------------------------ дерево
    def populate_tree(self, select=None):
        """Перестраивает дерево и открывает нужный тир-лист."""
        if select is None:
            select = (self.current_folder, self.current_list)
            if select == (None, None):
                select = tuple(self.workspace_data.get("last_opened") or [None, None])

        self.tree.blockSignals(True)
        self.tree.clear()
        folder_icon = Icons.icon("folder", 18, ACCENT_HI)
        list_icon = Icons.icon("tierlist", 18)
        item_to_select, first_list = None, None

        for folder_name, lists_dict in self.workspace_data["folders"].items():
            if not isinstance(lists_dict, dict):
                continue
            f_item = QTreeWidgetItem(self.tree, [folder_name])
            f_item.setIcon(0, folder_icon)
            f_item.setData(0, Qt.ItemDataRole.UserRole, ["folder", folder_name])
            font = f_item.font(0)
            font.setBold(True)
            f_item.setFont(0, font)
            f_item.setExpanded(True)
            for list_name in lists_dict.keys():
                l_item = QTreeWidgetItem(f_item, [list_name])
                l_item.setIcon(0, list_icon)
                l_item.setData(0, Qt.ItemDataRole.UserRole, ["list", folder_name, list_name])
                if first_list is None:
                    first_list = l_item
                if (folder_name, list_name) == tuple(select):
                    item_to_select = l_item

        target = item_to_select or first_list
        if target is not None:
            self.tree.setCurrentItem(target)
        self.tree.blockSignals(False)

        if target is not None:
            _, f_name, l_name = target.data(0, Qt.ItemDataRole.UserRole)
            if (f_name, l_name) != (self.current_folder, self.current_list) or not self._board_ready:
                self.load_tier_list(f_name, l_name)
        else:
            self.load_tier_list(None, None)

    def _tree_item_data(self, item=None):
        item = item or self.tree.currentItem()
        return list(item.data(0, Qt.ItemDataRole.UserRole) or []) if item else []

    def on_tree_current_changed(self, current, previous):
        data = self._tree_item_data(current)
        if data and data[0] == "list":
            if (data[1], data[2]) != (self.current_folder, self.current_list):
                self.load_tier_list(data[1], data[2])

    def on_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            self.tree.setCurrentItem(item)
            data = self._tree_item_data(item)
            menu.addAction(Icons.icon("edit", 16), "Переименовать\tF2", self.rename_selected_tree_item)
            if data[0] == "list":
                menu.addAction(Icons.icon("copy", 16), "Дублировать", self.duplicate_selected_list)
                folders = [f for f in self.workspace_data["folders"] if f != data[1]]
                if folders:
                    sub = menu.addMenu(Icons.icon("folder", 16, MUTED), "Переместить в папку")
                    for f in folders:
                        sub.addAction(f, lambda f=f, d=data: self.move_list_to_folder(d[1], d[2], f))
            else:
                menu.addAction(Icons.icon("plus", 16), "Новый тир-лист здесь",
                               lambda d=data: self.create_tier_list(d[1]))
            menu.addSeparator()
            menu.addAction(Icons.icon("trash", 16, DANGER), "Удалить\tDel", self.delete_selected_tree_item)
        else:
            menu.addAction(Icons.icon("plus", 16), "Новый тир-лист", self.create_tier_list)
            menu.addAction(Icons.icon("folder", 16, MUTED), "Новая папка", self.create_folder)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    @staticmethod
    def _rename_key(d: dict, old, new):
        """Переименовывает ключ, сохраняя порядок."""
        items = [(new if k == old else k, v) for k, v in d.items()]
        d.clear()
        d.update(items)

    def _ask_name(self, title, label, text=""):
        name, ok = QInputDialog.getText(self, title, label, text=text)
        name = (name or "").strip()
        return name if ok and name else None

    def create_folder(self):
        name = self._ask_name("Новая папка", "Название папки:")
        if not name:
            return
        if name in self.workspace_data["folders"]:
            QMessageBox.warning(self, "Ошибка", "Такая папка уже существует!")
            return
        self.workspace_data["folders"][name] = {}
        self.save_workspace_data()
        self.populate_tree()

    def create_tier_list(self, folder=None):
        folders = self.workspace_data["folders"]
        if not folders:
            folders["Мои Тир-листы"] = {}
        if not folder or folder not in folders:
            data = self._tree_item_data()
            folder = data[1] if data else self.current_folder
            if folder not in folders:
                folder = next(iter(folders))

        name = self._ask_name("Новый тир-лист", f"Название тир-листа (папка «{folder}»):")
        if not name:
            return
        if name in folders[folder]:
            QMessageBox.warning(self, "Ошибка", "В этой папке уже есть тир-лист с таким именем!")
            return
        folders[folder][name] = _empty_board()
        self.save_workspace_data()
        self.populate_tree(select=(folder, name))
        self.focus_search()

    def rename_selected_tree_item(self):
        data = self._tree_item_data()
        if not data:
            return
        folders = self.workspace_data["folders"]
        if data[0] == "folder":
            old = data[1]
            new = self._ask_name("Переименовать папку", "Новое название:", old)
            if not new or new == old:
                return
            if new in folders:
                QMessageBox.warning(self, "Ошибка", "Такая папка уже существует!")
                return
            self._rename_key(folders, old, new)
            if self.current_folder == old:
                self.current_folder = new
        else:
            _, folder, old = data
            new = self._ask_name("Переименовать тир-лист", "Новое название:", old)
            if not new or new == old:
                return
            if new in folders[folder]:
                QMessageBox.warning(self, "Ошибка", "В этой папке уже есть тир-лист с таким именем!")
                return
            self._rename_key(folders[folder], old, new)
            if (self.current_folder, self.current_list) == (folder, old):
                self.current_list = new
        if self.current_board() is not None:
            self.workspace_data["last_opened"] = [self.current_folder, self.current_list]
            self._update_titles()
        self.save_workspace_data()
        self.populate_tree()

    def duplicate_selected_list(self):
        data = self._tree_item_data()
        if not data or data[0] != "list":
            return
        _, folder, name = data
        boards = self.workspace_data["folders"][folder]
        new_name, n = f"{name} (копия)", 2
        while new_name in boards:
            new_name = f"{name} (копия {n})"
            n += 1
        boards[new_name] = copy.deepcopy(boards[name])
        self.save_workspace_data()
        self.populate_tree(select=(folder, new_name))

    def move_list_to_folder(self, folder, name, target_folder):
        folders = self.workspace_data["folders"]
        if name in folders[target_folder]:
            QMessageBox.warning(self, "Ошибка", f"В папке «{target_folder}» уже есть тир-лист с таким именем!")
            return
        was_current = (self.current_folder, self.current_list) == (folder, name)
        folders[target_folder][name] = folders[folder].pop(name)
        if was_current:
            self.current_folder = target_folder
            self.workspace_data["last_opened"] = [target_folder, name]
            self._update_titles()
        self.save_workspace_data()
        self.populate_tree()

    def delete_selected_tree_item(self):
        data = self._tree_item_data()
        if not data:
            return
        folders = self.workspace_data["folders"]

        if data[0] == "folder":
            folder_name = data[1]
            n = len(folders.get(folder_name, {}))
            text = f"Удалить папку «{folder_name}»"
            text += f" и все тир-листы в ней ({n} шт.)?" if n else "?"
        else:
            _, folder_name, list_name = data
            n_games = len(folders[folder_name][list_name].get("games_info", {}))
            text = f"Удалить тир-лист «{list_name}»" + (f" ({n_games} игр)?" if n_games else "?")
        text += "\n\nЭто действие нельзя отменить."

        box = QMessageBox(QMessageBox.Icon.Warning, "Удаление", text, parent=self)
        btn_del = box.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole))
        box.exec()
        if box.clickedButton() is not btn_del:
            return

        if data[0] == "folder":
            del folders[folder_name]
            if self.current_folder == folder_name:
                self.current_folder, self.current_list = None, None
        else:
            del folders[folder_name][list_name]
            if (self.current_folder, self.current_list) == (folder_name, list_name):
                self.current_folder, self.current_list = None, None
        if self.current_folder is None:
            self._board_ready = False
        self.save_workspace_data()
        self.populate_tree()

    # ------------------------------------------------------------------ доска
    def _update_titles(self):
        if self.current_board() is None:
            self.lbl_folder.setText("")
            self.lbl_current_title.setText("Создай тир-лист слева")
        else:
            self.lbl_current_title.setText(self.current_list)
            self._update_counts()

    def load_tier_list(self, folder_name, list_name):
        self._board_ready = False
        self.undo_stack.clear()
        self.btn_undo.setEnabled(False)
        self.current_folder, self.current_list = folder_name, list_name

        if self.current_board() is None:
            self.current_folder, self.current_list = None, None
            self._clear_board_widgets()
            self._set_board_enabled(False)
            self._update_titles()
            self._update_counts()
            return

        self._set_board_enabled(True)
        if self.workspace_data.get("last_opened") != [folder_name, list_name]:
            self.workspace_data["last_opened"] = [folder_name, list_name]
            self.save_workspace_data()
        self._render_board()
        self.tiers_scroll.verticalScrollBar().setValue(0)

    def _clear_board_widgets(self):
        for row in self.tier_rows.values():
            row.drop_zone.clear_cards()
        self.pool_zone.clear_cards()
        self.card_widgets.clear()

    def _render_board(self):
        """Пересоздаёт карточки по данным текущего тир-листа."""
        self._board_ready = False
        self._clear_board_widgets()
        board = self.current_board()
        if board is None:
            return
        games_info = board["games_info"]
        seen = set()

        def place(zone, ids):
            for gid in ids:
                if not isinstance(gid, str) or gid in seen:
                    continue
                seen.add(gid)
                zone.add_card(self._create_card_widget(gid, games_info.get(gid) or {}))

        for letter, row in self.tier_rows.items():
            place(row.drop_zone, board["tiers"].get(letter, []))
        place(self.pool_zone, board["pool"])
        # Игры, которые есть в games_info, но никуда не разложены — не теряем, кладём вниз
        place(self.pool_zone, [gid for gid in games_info if gid not in seen])

        self._board_ready = True
        self._update_titles()

    def _create_card_widget(self, game_id, info):
        card = GameCard(game_id, info.get("name") or game_id, info.get("image_path") or "")
        card.removed.connect(self.remove_game_from_board)
        card.move_requested.connect(self.move_card)
        self.card_widgets[game_id] = card
        return card

    def find_card_widget(self, game_id):
        return self.card_widgets.get(game_id)

    def _zone_by_id(self, zone_id):
        if zone_id == "POOL":
            return self.pool_zone
        row = self.tier_rows.get(zone_id)
        return row.drop_zone if row else None

    def move_card(self, game_id, zone_id):
        card = self.card_widgets.get(game_id)
        target = self._zone_by_id(zone_id)
        if not card or not target or card.parentWidget() is target:
            return
        self.push_undo()
        old = card.parentWidget()
        if isinstance(old, TierDropZone):
            old.take_card(card)
        target.add_card(card, animate=True)
        self.sync_current_board_to_data()

    def remove_game_from_board(self, game_id):
        board = self.current_board()
        card = self.card_widgets.get(game_id)
        if board is None or card is None:
            return
        self.push_undo()
        self.card_widgets.pop(game_id, None)
        parent = card.parentWidget()
        if isinstance(parent, TierDropZone):
            parent.take_card(card)
        card.hide()
        card.deleteLater()
        board["games_info"].pop(game_id, None)
        self.sync_current_board_to_data()
        self.set_status(f"Удалено: {card.game_name}  ·  Ctrl+Z — вернуть")

    def return_all_to_pool(self):
        if self.current_board() is None:
            return
        cards = [c for row in self.tier_rows.values() for c in row.drop_zone.cards()]
        if not cards:
            return
        self.push_undo()
        for card in cards:
            card.parentWidget().take_card(card)
            self.pool_zone.add_card(card, animate=True)
        self.sync_current_board_to_data()
        self.set_status("Все игры сброшены вниз  ·  Ctrl+Z — вернуть")

    def add_game(self, target, gid, name, image_path):
        """Добавляет игру в тир-лист target=(папка, список), даже если сейчас открыт другой."""
        folder, list_name = target
        board = self.workspace_data["folders"].get(folder, {}).get(list_name)
        if board is None:
            self.set_status("Тир-лист был удалён — игра не добавлена", error=True)
            return False
        if gid in board["games_info"]:
            self.set_status(f"«{name}» уже в списке")
            return False

        is_current = (folder, list_name) == (self.current_folder, self.current_list) and self._board_ready
        if is_current:
            self.push_undo()
        board["games_info"][gid] = {"name": name, "image_path": image_path}
        if is_current:
            card = self._create_card_widget(gid, board["games_info"][gid])
            self.pool_zone.add_card(card, animate=True)
            self.sync_current_board_to_data()
            QTimer.singleShot(0, lambda: self.pool_scroll.ensureWidgetVisible(card) if card in self.card_widgets.values() else None)
        else:
            board["pool"].append(gid)
            self.save_workspace_data()
        self.set_status(f"Добавлено: {name}")
        return True

    # ------------------------------------------------------------------ своя картинка
    def add_custom_game_from_pc(self):
        if self.current_board() is None:
            QMessageBox.information(self, "Нет тир-листа", "Сначала создай или выбери тир-лист слева.")
            return
        target = (self.current_folder, self.current_list)

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбери обложку игры", "", "Картинки (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
        )
        if not file_path:
            return
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        name = self._ask_name("Название игры", "Название игры:", default_name)
        if not name:
            return

        gid = "custom_" + hashlib.md5(f"{name}_{file_path}".encode("utf-8")).hexdigest()[:10]
        save_path = os.path.join(CACHE_DIR, f"{gid}.png")
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            make_square_cover(file_path, save_path)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось обработать картинку:\n{e}")
            return
        self.add_game(target, gid, name, save_path)

    # ------------------------------------------------------------------ экспорт
    def render_board_pixmap(self) -> QPixmap:
        scale, pad, title_h = 2.0, 28, 64
        board = self.board_frame
        w, h = board.width() + pad * 2, board.height() + pad * 2 + title_h
        pix = QPixmap(int(w * scale), int(h * scale))
        pix.setDevicePixelRatio(scale)
        pix.fill(QColor(BG))

        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        p.drawText(QRectF(pad + 2, pad - 6, w - pad * 2, title_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.current_list or "")
        p.end()
        board.render(pix, QPoint(pad, pad + title_h), flags=QWidget.RenderFlag.DrawChildren)
        return pix

    def export_png(self):
        if self.current_board() is None:
            return
        safe = re.sub(r'[\\/:*?"<>|]', "_", self.current_list)
        s = QSettings(UI_STATE_FILE, QSettings.Format.IniFormat)
        start_dir = s.value("export_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить тир-лист", os.path.join(str(start_dir), f"{safe}.png"), "PNG (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if self.render_board_pixmap().save(path, "PNG"):
            s.setValue("export_dir", os.path.dirname(path))
            self.set_status(f"Сохранено: {os.path.basename(path)}")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить картинку.")

    def copy_board_image(self):
        if self.current_board() is None:
            return
        QApplication.clipboard().setPixmap(self.render_board_pixmap())
        self.set_status("Картинка скопирована в буфер")

    # ------------------------------------------------------------------ поиск
    def _track_thread(self, thread: QThread):
        """Держим ссылку на поток, пока он не завершится (иначе Qt роняет приложение)."""
        self._threads.add(thread)
        thread.finished.connect(lambda t=thread: self._threads.discard(t))

    def on_search_text_changed(self, text):
        query = text.strip()
        self.btn_clear_search.setVisible(bool(text))
        if len(query) < 2:
            self.search_timer.stop()
            if self.live_search_worker:
                self.live_search_worker.abort()
            self.set_status("", timeout=0)
            self.suggestions_popup.hide()
            return
        if query.lower() in SEARCH_MEM_CACHE:
            self.search_timer.stop()
            self.start_live_search()
            return
        self.set_status("Поиск…", timeout=0)
        self.search_timer.start()

    def clear_live_search(self):
        self.search_input.clear()
        self.suggestions_popup.hide()
        self.search_input.setFocus()

    def start_live_search(self):
        query = self.search_input.text().strip()
        if len(query) < 2 or self._closing:
            return
        if self.live_search_worker:
            self.live_search_worker.abort()

        worker = LiveSearchWorker(query)
        worker.results_ready.connect(self.on_live_search_results)
        worker.thumb_ready.connect(self.suggestions_popup.update_thumbnail)
        self._track_thread(worker)
        self.live_search_worker = worker
        worker.start()

    def on_live_search_results(self, query, results):
        if self._closing or query != self.search_input.text().strip():
            return
        if not results:
            self.set_status("Ничего не найдено", timeout=0)
            self.suggestions_popup.hide()
            return
        self.set_status(f"Найдено: {len(results)}  ·  ↑↓ Enter", timeout=0)
        board = self.current_board()
        added = board["games_info"] if board else {}
        self.suggestions_popup.show_results(results, added, self.search_box)

    def on_suggestion_clicked(self, game_data):
        if self.current_board() is None:
            QMessageBox.information(self, "Нет тир-листа", "Сначала создай или выбери тир-лист слева.")
            return

        self.suggestions_popup.hide()
        self.search_timer.stop()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.btn_clear_search.hide()
        self.search_input.setFocus()

        if game_data["id"] in self.current_board()["games_info"]:
            self.set_status(f"«{game_data['name']}» уже в списке")
            return

        self.set_status(f"Добавляем «{game_data['name']}»…", timeout=0)
        worker = ImageDownloadWorker(game_data, (self.current_folder, self.current_list))
        worker.done.connect(self.on_game_downloaded)
        worker.failed.connect(lambda msg: self.set_status(msg, error=True))
        self._track_thread(worker)
        worker.start()

    def on_game_downloaded(self, game_data):
        if self._closing:
            return
        worker = self.sender()
        target = getattr(worker, "target", (self.current_folder, self.current_list))
        self.add_game(target, game_data["id"], game_data["name"], game_data["image_path"])


# ============================================================================
#  ЗАПУСК
# ============================================================================
def install_excepthook():
    """Необработанная ошибка в слоте больше не закрывает приложение молча."""
    state = {"showing": False}

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(time.strftime("\n===== %Y-%m-%d %H:%M:%S =====\n") + text)
        except Exception:
            pass
        sys.__stderr__ and sys.__stderr__.write(text)
        if state["showing"] or QApplication.instance() is None:
            return
        state["showing"] = True
        try:
            box = QMessageBox(QMessageBox.Icon.Critical, "Ошибка",
                              "Произошла ошибка, но приложение продолжает работать.\n"
                              f"Подробности записаны в файл:\n{ERROR_LOG}")
            box.setDetailedText(text)
            box.exec()
        finally:
            state["showing"] = False

    sys.excepthook = hook


def main():
    install_excepthook()
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tiermaker.pro.games.1")
    except Exception:
        pass
    app = QApplication(sys.argv)
    apply_dark_palette(app)
    window = TierMakerApp()
    window.show()
    if os.environ.get("TIERMAKER_SELFTEST"):
        _run_selftest(app, window)
    sys.exit(app.exec())


def _run_selftest(app, window):
    """Проверка сборки: поиск + скачивание обложки, результат в selftest.json, затем выход."""
    report = {"results": 0, "sources": [], "thumbs": 0, "added": False, "status": ""}

    def finish():
        board = window.current_board() or {}
        report["added"] = any(os.path.isfile(resolve_image_path(i.get("image_path", "")))
                              for i in board.get("games_info", {}).values())
        report["status"] = window.lbl_search_status.text()
        with open(os.path.join(DATA_DIR, "selftest.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
        window.close()
        app.quit()

    def pick():
        rows = window.suggestions_popup.rows
        report["results"] = len(rows)
        report["sources"] = sorted({r.game_data.get("source") for r in rows})
        report["thumbs"] = sum(1 for r in rows if r._thumb is not None)
        if rows:
            window.suggestions_popup.activate_selected()
        QTimer.singleShot(9000, finish)

    window.search_input.setText("portal")
    QTimer.singleShot(9000, pick)


if __name__ == "__main__":
    main()
