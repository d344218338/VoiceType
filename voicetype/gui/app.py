"""VoiceType 启动器 - 主界面 + 设置 + 系统托盘后台运行"""
import sys
import os
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QDialog, QTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QTabWidget, QFrame, QStackedWidget, QSizePolicy,
    QCheckBox, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QEvent
from PyQt6.QtGui import (
    QIcon, QPixmap, QAction, QFont, QColor, QPainter, QPainterPath,
    QKeySequence, QLinearGradient, QPen,
)

from voicetype.core.config import load_config, save_config, load_state, save_state, EDITION, APP_DIR
from voicetype.core.engine import VoiceTypeEngine, VoiceMode
from voicetype.gui.hotkeys import HotkeyManager
from voicetype.gui.donation import should_show_donation, mark_donation_shown


# ─── 全局样式 ─────────────────────────────────────────
STYLE = """
* {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}
QMainWindow, QDialog {
    background: #0f0f13;
}

/* ── 侧边栏 ── */
#sidebar {
    background: #16161d;
    border-right: 1px solid #2a2a35;
}
#sidebar QPushButton {
    background: transparent;
    color: #8888a0;
    border: none;
    border-radius: 10px;
    padding: 14px 18px;
    text-align: left;
    font-size: 14px;
}
#sidebar QPushButton:hover {
    background: #1e1e2a;
    color: #c0c0d0;
}
#sidebar QPushButton[active="true"] {
    background: #1e1e2a;
    color: #ffffff;
    border-left: 3px solid #6366f1;
}

/* ── 内容区 ── */
#content {
    background: #0f0f13;
}

/* ── 卡片 ── */
.card {
    background: #16161d;
    border: 1px solid #2a2a35;
    border-radius: 12px;
    padding: 20px;
}
.card:hover {
    border-color: #3a3a50;
}

/* ── 按钮 ── */
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5558e6, stop:1 #7c4fe0);
}
QPushButton#secondary {
    background: #1e1e2a;
    color: #c0c0d0;
    border: 1px solid #2a2a35;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 13px;
}
QPushButton#secondary:hover {
    background: #2a2a38;
    border-color: #4a4a60;
}

/* ── 输入框 ── */
QLineEdit, QComboBox {
    background: #1a1a24;
    color: #e0e0ee;
    border: 1px solid #2a2a35;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: #6366f1;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #6366f1;
}
QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}
QComboBox QAbstractItemView {
    background: #1a1a24;
    color: #e0e0ee;
    border: 1px solid #2a2a35;
    selection-background-color: #6366f1;
}

/* ── 快捷键录入按钮 ── */
QPushButton.hotkey-btn {
    background: #1a1a24;
    color: #e0e0ee;
    border: 1px solid #2a2a35;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 13px;
    font-family: "Consolas", "Courier New", monospace;
    text-align: center;
}
QPushButton.hotkey-btn:hover {
    border-color: #6366f1;
}
QPushButton.hotkey-btn[recording="true"] {
    border-color: #ef4444;
    color: #ef4444;
    background: #1a1015;
}

/* ── 标签 ── */
QLabel {
    color: #c0c0d0;
}
QLabel#title {
    color: #ffffff;
    font-size: 22px;
    font-weight: bold;
}
QLabel#subtitle {
    color: #6b6b80;
    font-size: 13px;
}
QLabel#section-title {
    color: #ffffff;
    font-size: 16px;
    font-weight: bold;
}
QLabel#hint {
    color: #55556a;
    font-size: 12px;
}
QLabel#status-ok {
    color: #22c55e;
    font-size: 13px;
}
QLabel#status-warn {
    color: #eab308;
    font-size: 13px;
}
QLabel#status-err {
    color: #ef4444;
    font-size: 13px;
}

QCheckBox {
    color: #c0c0d0;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 1px solid #2a2a35;
    background: #1a1a24;
}
QCheckBox::indicator:checked {
    background: #6366f1;
    border-color: #6366f1;
}

QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #0f0f13;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: #2a2a35;
    border-radius: 3px;
    min-height: 30px;
}
"""


# ─── 信号桥接 ─────────────────────────────────────────
class SignalBridge(QObject):
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str, str)  # text, mode_name
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal()
    error_signal = pyqtSignal(str)
    init_done = pyqtSignal(bool, str)  # success, message


# ─── 快捷键录入按钮 ──────────────────────────────────
class HotkeyButton(QPushButton):
    """
    点击后按下想要的快捷键组合来录入。
    使用 pynput 底层监听，可以区分左右 Alt/Ctrl/Shift。
    """
    hotkey_changed = pyqtSignal(str)

    def __init__(self, current_hotkey: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", "hotkey-btn")
        self._hotkey = current_hotkey
        self._recording = False
        self._pressed = set()        # 当前按住的键名
        self._pynput_listener = None
        self._update_display()
        self.setFixedHeight(42)
        self.setMinimumWidth(200)
        self.clicked.connect(self._toggle_recording)

    # ── 显示 ──
    DISPLAY_MAP = {
        "ralt": "右Alt", "lalt": "左Alt", "alt": "Alt",
        "rctrl": "右Ctrl", "lctrl": "左Ctrl", "ctrl": "Ctrl",
        "rshift": "右Shift", "lshift": "左Shift", "shift": "Shift",
    }

    def _update_display(self):
        if self._recording:
            self.setText(">> 请按下快捷键组合 <<")
            self.setProperty("recording", "true")
        else:
            if self._hotkey:
                parts = self._hotkey.split("+")
                display_parts = [self.DISPLAY_MAP.get(p, p.upper()) for p in parts]
                self.setText(" + ".join(display_parts))
            else:
                self.setText("点击此处设置快捷键")
            self.setProperty("recording", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # ── 录入控制 ──
    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._pressed = set()
        self._update_display()

        from pynput import keyboard as kb

        def on_press(key):
            if not self._recording:
                return False
            name = self._key_to_name(key)
            if name == "esc":
                self._stop_recording()
                return False
            if name:
                self._pressed.add(name)

        def on_release(key):
            if not self._recording:
                return False
            name = self._key_to_name(key)

            if not self._pressed:
                return

            # 支持三种情况：
            # 1. 单个修饰键（如 ralt）
            # 2. 修饰键+修饰键（如 ralt+rshift）
            # 3. 修饰键+普通键（如 ralt+space, ctrl+t）
            modifier_keys = {"ctrl", "lctrl", "rctrl", "alt", "lalt", "ralt",
                             "shift", "lshift", "rshift", "win"}
            has_mod = any(p in modifier_keys for p in self._pressed)

            if has_mod and len(self._pressed) >= 1:
                mods = sorted([p for p in self._pressed if p in modifier_keys])
                keys = sorted([p for p in self._pressed if p not in modifier_keys])
                self._hotkey = "+".join(mods + keys)
                QTimer.singleShot(0, self._finish_recording)
                return False  # 停止监听

        self._pynput_listener = kb.Listener(on_press=on_press, on_release=on_release)
        self._pynput_listener.daemon = True
        self._pynput_listener.start()

    def _finish_recording(self):
        self._recording = False
        self._update_display()
        self.hotkey_changed.emit(self._hotkey)

    def _stop_recording(self):
        self._recording = False
        if self._pynput_listener:
            self._pynput_listener.stop()
            self._pynput_listener = None
        QTimer.singleShot(0, self._update_display)

    def _key_to_name(self, key) -> str:
        """把 pynput 的 key 对象转为我们的名称"""
        from pynput import keyboard as kb

        # 右 Alt (Windows 上可能是 alt_r 或 alt_gr 或 vk=165)
        if key == kb.Key.alt_r or key == kb.Key.alt_gr:
            return "ralt"
        if hasattr(key, "vk") and key.vk == 165:
            return "ralt"
        # 左 Alt
        if key == kb.Key.alt_l:
            return "lalt"
        if hasattr(key, "vk") and key.vk == 164:
            return "lalt"

        SPECIAL = {
            kb.Key.ctrl_l: "lctrl", kb.Key.ctrl_r: "rctrl",
            kb.Key.shift_l: "lshift", kb.Key.shift_r: "rshift",
            kb.Key.cmd: "win", kb.Key.cmd_r: "win",
            kb.Key.space: "space", kb.Key.enter: "enter",
            kb.Key.tab: "tab", kb.Key.esc: "esc",
            kb.Key.backspace: "backspace", kb.Key.delete: "delete",
            kb.Key.up: "up", kb.Key.down: "down",
            kb.Key.left: "left", kb.Key.right: "right",
            kb.Key.f1: "f1", kb.Key.f2: "f2", kb.Key.f3: "f3",
            kb.Key.f4: "f4", kb.Key.f5: "f5", kb.Key.f6: "f6",
            kb.Key.f7: "f7", kb.Key.f8: "f8", kb.Key.f9: "f9",
            kb.Key.f10: "f10", kb.Key.f11: "f11", kb.Key.f12: "f12",
        }
        if key in SPECIAL:
            return SPECIAL[key]

        # 普通字符键
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        if hasattr(key, "vk") and key.vk:
            # 字母数字键的 vk
            vk = key.vk
            if 0x30 <= vk <= 0x39:  # 0-9
                return chr(vk)
            if 0x41 <= vk <= 0x5A:  # A-Z
                return chr(vk).lower()

        return ""

    def focusOutEvent(self, event):
        if self._recording:
            self._stop_recording()
        super().focusOutEvent(event)

    def get_hotkey(self) -> str:
        return self._hotkey


# ─── 悬浮录音面板 ────────────────────────────────────────
class FloatingBar(QWidget):
    """录音状态面板 - 屏幕正中显示，大尺寸，美观"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 140)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 上部：计时器
        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Consolas", 32, QFont.Weight.Bold))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: white; background: transparent;")
        main_layout.addWidget(self.time_label)

        # 下部：状态文字
        self.status_label = QLabel("VoiceType 就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 12))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,0.8); background: transparent; padding: 6px 20px;"
        )
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._elapsed = 0
        self._is_recording = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 20, 20)
        if self._is_recording:
            # 录音中：红色渐变
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0, QColor(180, 30, 30, 240))
            grad.setColorAt(1, QColor(140, 20, 50, 240))
            p.fillPath(path, grad)
        else:
            # 处理中：深色
            p.fillPath(path, QColor(22, 22, 35, 240))
        # 边框
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.5))
        p.drawPath(path)

    def show_centered(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2 - 60
        self.move(x, y)
        self.show()
        self.raise_()

    def set_status(self, text, icon=""):
        self.status_label.setText(text)
        self.show_centered()

    def start_recording(self, mode_name):
        self._is_recording = True
        self._elapsed = 0
        self.time_label.setText("00:00")
        self.time_label.show()
        self.status_label.setText(f"正在录音 - {mode_name}\n再按一次快捷键停止")
        self._timer.start(1000)
        self.show_centered()
        self.update()

    def stop_recording(self):
        self._is_recording = False
        self._timer.stop()
        self.time_label.setText("")
        self.time_label.hide()
        self.status_label.setText("AI 处理中...")
        self.show_centered()
        self.update()

    def _tick(self):
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self.time_label.setText(f"{m:02d}:{s:02d}")

    def show_result(self, text):
        self._is_recording = False
        self.time_label.hide()
        preview = text[:60] + "..." if len(text) > 60 else text
        self.status_label.setText(preview)
        self.show_centered()
        self.update()
        QTimer.singleShot(3000, self.hide)


# ─── 结果弹窗 ──────────────────────────────────────────
class ResultDialog(QDialog):
    def __init__(self, text, mode_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"VoiceType - {mode_name}")
        self.setMinimumSize(520, 320)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel(mode_name)
        header.setObjectName("section-title")
        layout.addWidget(header)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(
            "background: #1a1a24; color: #e0e0ee; border: 1px solid #2a2a35;"
            "border-radius: 10px; padding: 14px; font-size: 14px; line-height: 1.6;"
        )
        layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_copy = QPushButton("复制到剪贴板")
        btn_copy.setObjectName("primary")
        btn_copy.clicked.connect(lambda: (
            QApplication.clipboard().setText(text),
            btn_copy.setText("已复制!"),
            QTimer.singleShot(1500, lambda: btn_copy.setText("复制到剪贴板")),
        ))
        btn_row.addWidget(btn_copy)

        btn_close = QPushButton("关闭")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


# ─── 打赏弹窗 ──────────────────────────────────────────
class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("支持 VoiceType")
        self.setFixedSize(380, 440)
        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QLabel { color: #333; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(32, 24, 32, 24)

        title = QLabel("感谢使用 VoiceType!")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("VoiceType 完全免费。\n如果觉得好用，可以请作者喝杯咖啡 :)")
        desc.setFont(QFont("Microsoft YaHei", 12))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        qr_label = QLabel()
        qr_label.setFixedSize(200, 200)
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_label.setStyleSheet("background: #f5f5f5; border: 2px dashed #ddd; border-radius: 10px;")
        qr_path = os.path.join(os.path.dirname(__file__), "..", "assets", "donation_qr.png")
        if os.path.exists(qr_path):
            px = QPixmap(qr_path)
            qr_label.setPixmap(px.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        else:
            qr_label.setText("收款码图片\n(assets/donation_qr.png)")
        layout.addWidget(qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("关闭后不再弹出，不影响正常使用")
        hint.setStyleSheet("color: #aaa; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        btn = QPushButton("我知道了")
        btn.setStyleSheet(
            "background: #6366f1; color: white; border: none;"
            "border-radius: 8px; padding: 12px 40px; font-size: 14px;"
        )
        btn.clicked.connect(lambda: (mark_donation_shown(), self.accept()))
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def closeEvent(self, event):
        mark_donation_shown()
        super().closeEvent(event)


# ─── 主页面 ────────────────────────────────────────────
def _make_card(parent=None):
    frame = QFrame(parent)
    frame.setProperty("class", "card")
    frame.setStyleSheet(
        "QFrame { background: #16161d; border: 1px solid #2a2a35;"
        "border-radius: 12px; padding: 0px; }"
    )
    return frame


class HomePage(QWidget):
    """首页 - 功能说明 + 状态"""
    def __init__(self, config, signals):
        super().__init__()
        self.config = config
        self.signals = signals

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 28, 32, 28)

        # 标题
        title = QLabel("VoiceType 语音助手")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("按住快捷键说话，松开即可得到结果。支持语音整理、翻译、AI问答。")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # ── 三个功能卡片 ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        cards_data = [
            ("语音整理", config["hotkey_transcribe"],
             "按一下开始录音，再按一下停止。\nAI 自动把你说的内容整理成书面\n文字，直接输入到当前窗口。\n\n适合：写文档、发消息、记笔记",
             "#6366f1"),
            ("语音翻译", config["hotkey_translate"],
             "按一下开始录音，再按一下停止。\n自动翻译成你设定的目标语言，\n直接输入到当前窗口。\n\n适合：跨语言沟通、学外语",
             "#8b5cf6"),
            ("AI 改写", config["hotkey_assistant"],
             "先选中一段文字，按一下快捷键，\n然后说出你的指令（如「润色」），\n再按一下，AI 改写并自动替换。\n\n适合：润色文章、补充内容、改写",
             "#a855f7"),
        ]

        for name, hotkey, desc, color in cards_data:
            card = _make_card()
            cl = QVBoxLayout(card)
            cl.setSpacing(10)
            cl.setContentsMargins(20, 20, 20, 20)

            dot = QLabel(f"●  {name}")
            dot.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold;")
            cl.addWidget(dot)

            hk_display = hotkey.replace("+", " + ").upper()
            hk = QLabel(f"快捷键:  {hk_display}")
            hk.setStyleSheet(
                "background: #0f0f13; color: #9999b0; border-radius: 6px;"
                "padding: 6px 10px; font-size: 12px; font-family: Consolas;"
            )
            cl.addWidget(hk)

            d = QLabel(desc)
            d.setStyleSheet("color: #7777a0; font-size: 12px; line-height: 1.5;")
            d.setWordWrap(True)
            cl.addWidget(d)

            cl.addStretch()
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        layout.addSpacing(8)

        # ── 使用说明 ──
        guide_title = QLabel("怎么用？")
        guide_title.setObjectName("section-title")
        layout.addWidget(guide_title)

        steps = [
            "1.  确保本程序在后台运行（关闭窗口会自动缩到托盘）",
            "2.  在任何地方按一下快捷键 → 开始录音，对着麦克风说话",
            "3.  说完再按一下同样的快捷键 → 停止录音",
            "4.  等待几秒，结果会自动输入到你当前的窗口中",
            "",
            "AI 改写用法：先用鼠标选中一段文字 → 按快捷键 → 说出指令",
            "（比如「帮我润色」「精简一下」「补充完善」）→ 再按一下快捷键",
            "",
            "快捷键可以在左侧「快捷键设置」中自由修改",
        ]
        for step in steps:
            sl = QLabel(step)
            sl.setStyleSheet("color: #8888a0; font-size: 13px; padding: 2px 0;")
            sl.setWordWrap(True)
            layout.addWidget(sl)

        layout.addSpacing(8)

        # ── 状态 ──
        status_title = QLabel("运行状态")
        status_title.setObjectName("section-title")
        layout.addWidget(status_title)

        self.status_label = QLabel("正在初始化...")
        self.status_label.setObjectName("status-warn")
        layout.addWidget(self.status_label)

        layout.addStretch()

        scroll.setWidget(scroll_widget)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # 连接状态信号
        self.signals.init_done.connect(self._on_init_done)

    def _on_init_done(self, success, msg):
        if success:
            self.status_label.setText(msg)
            self.status_label.setObjectName("status-ok")
        else:
            self.status_label.setText(msg)
            self.status_label.setObjectName("status-err")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def refresh_hotkeys(self, config):
        """刷新卡片上的快捷键显示 - 简单方案：更新config引用"""
        self.config = config


class HotkeyPage(QWidget):
    """快捷键设置页"""
    hotkeys_saved = pyqtSignal()  # 保存后通知主应用重载快捷键

    def __init__(self, config):
        super().__init__()
        self.config = config

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 28, 32, 28)

        title = QLabel("快捷键设置")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("点击下方按钮，然后按下你想要的快捷键组合（比如 Ctrl+Alt+某个键）。")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ── 三个快捷键设置 ──
        hotkeys_data = [
            ("语音整理", "hotkey_transcribe",
             "按一下开始说话 → 再按一下停止 → 自动输入到当前窗口",
             "用途举例：在微信输入框按一下快捷键，说「今天开会讨论了项目进度」，\n"
             "再按一下，自动把整理好的文字打到微信里。"),
            ("语音翻译", "hotkey_translate",
             "按一下开始说话 → 再按一下停止 → 翻译结果自动输入",
             "用途举例：说中文，自动翻译成英文输入到当前窗口。\n"
             "翻译的目标语言可以在「其他设置」中修改。"),
            ("AI 改写", "hotkey_assistant",
             "先选中文字 → 按一下说指令 → 再按一下 → AI 改写并替换",
             "用途举例：选中一段话，按快捷键，说「帮我润色一下」，\n"
             "再按一下，AI 会把选中的文字改写得更通顺、更有逻辑。"),
        ]

        self.hotkey_buttons = {}

        for name, key, desc, example in hotkeys_data:
            card = _make_card()
            cl = QVBoxLayout(card)
            cl.setSpacing(10)
            cl.setContentsMargins(24, 20, 24, 20)

            header_row = QHBoxLayout()
            label = QLabel(name)
            label.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold;")
            header_row.addWidget(label)

            desc_label = QLabel(f"  —  {desc}")
            desc_label.setStyleSheet("color: #6b6b80; font-size: 12px;")
            header_row.addWidget(desc_label)
            header_row.addStretch()
            cl.addLayout(header_row)

            # 快捷键按钮
            hk_row = QHBoxLayout()
            hk_label = QLabel("当前快捷键：")
            hk_label.setStyleSheet("color: #8888a0; font-size: 13px;")
            hk_row.addWidget(hk_label)

            btn = HotkeyButton(config.get(key, ""))
            self.hotkey_buttons[key] = btn
            hk_row.addWidget(btn)

            hk_hint = QLabel("  （点击按钮，然后按下新的快捷键组合）")
            hk_hint.setObjectName("hint")
            hk_row.addWidget(hk_hint)
            hk_row.addStretch()
            cl.addLayout(hk_row)

            ex = QLabel(example)
            ex.setStyleSheet("color: #55556a; font-size: 12px; line-height: 1.4;")
            ex.setWordWrap(True)
            cl.addWidget(ex)

            layout.addWidget(card)

        layout.addSpacing(12)

        # 提示
        tip_card = _make_card()
        tip_layout = QVBoxLayout(tip_card)
        tip_layout.setContentsMargins(24, 16, 24, 16)

        tip_title = QLabel("小贴士")
        tip_title.setStyleSheet("color: #eab308; font-size: 14px; font-weight: bold;")
        tip_layout.addWidget(tip_title)

        tips = [
            "• 快捷键需要包含至少一个修饰键（Ctrl / Alt / Shift）加一个普通键",
            "• 建议使用 右Alt+字母 的组合，不容易跟其他软件冲突",
            "• 修改后点击下方「保存」按钮生效",
            "• 按 Esc 可以取消当前录入",
        ]
        for t in tips:
            tl = QLabel(t)
            tl.setStyleSheet("color: #8888a0; font-size: 12px;")
            tip_layout.addWidget(tl)

        layout.addWidget(tip_card)

        # 保存按钮
        layout.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.save_btn = QPushButton("保存快捷键")
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setMinimumWidth(160)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

        scroll.setWidget(scroll_widget)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _save(self):
        for key, btn in self.hotkey_buttons.items():
            self.config[key] = btn.get_hotkey()
        save_config(self.config)
        self.save_btn.setText("已保存! 快捷键已生效")
        QTimer.singleShot(2000, lambda: self.save_btn.setText("保存快捷键"))
        self.hotkeys_saved.emit()


class SettingsPage(QWidget):
    """其他设置页"""
    def __init__(self, config):
        super().__init__()
        self.config = config

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 28, 32, 28)

        title = QLabel("其他设置")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("调整翻译语言、语音识别精度、AI 模型等参数。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ── 翻译设置 ──
        card1 = _make_card()
        c1 = QVBoxLayout(card1)
        c1.setSpacing(12)
        c1.setContentsMargins(24, 20, 24, 20)

        c1_title = QLabel("翻译设置")
        c1_title.setStyleSheet("color: #fff; font-size: 15px; font-weight: bold;")
        c1.addWidget(c1_title)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("翻译目标语言："))
        self.lang_combo = QComboBox()
        langs = {"en": "English (英语)", "zh": "中文", "ja": "日本語 (日语)",
                 "ko": "한국어 (韩语)", "fr": "Français (法语)", "de": "Deutsch (德语)",
                 "es": "Español (西班牙语)", "ru": "Русский (俄语)",
                 "pt": "Português (葡萄牙语)", "th": "ไทย (泰语)", "vi": "Tiếng Việt (越南语)"}
        for code, name in langs.items():
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(config["translate_target"])
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        row1.addWidget(self.lang_combo)
        row1.addStretch()
        c1.addLayout(row1)

        hint1 = QLabel("使用「语音翻译」时，你说的话会被翻译成上面选择的语言。")
        hint1.setObjectName("hint")
        c1.addWidget(hint1)

        layout.addWidget(card1)

        # ── 语音识别设置 ──
        card2 = _make_card()
        c2 = QVBoxLayout(card2)
        c2.setSpacing(12)
        c2.setContentsMargins(24, 20, 24, 20)

        c2_title = QLabel("语音识别精度")
        c2_title.setStyleSheet("color: #fff; font-size: 15px; font-weight: bold;")
        c2.addWidget(c2_title)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("识别模型："))
        self.whisper_combo = QComboBox()
        whisper_options = [
            ("tiny —— 最快，精度一般（约75MB）", "tiny"),
            ("base —— 较快，精度不错（约150MB）", "base"),
            ("small —— 中等速度，精度较高（约500MB）", "small"),
            ("medium —— 较慢，精度很高（约1.5GB）", "medium"),
            ("large-v3 —— 最慢，精度最高（约3GB）", "large-v3"),
        ]
        for display, value in whisper_options:
            self.whisper_combo.addItem(display, value)
        widx = self.whisper_combo.findData(config["whisper_model"])
        if widx >= 0:
            self.whisper_combo.setCurrentIndex(widx)
        row2.addWidget(self.whisper_combo)
        row2.addStretch()
        c2.addLayout(row2)

        row2b = QHBoxLayout()
        row2b.addWidget(QLabel("识别语言："))
        self.src_lang = QComboBox()
        src_langs = [("自动检测（推荐）", "auto"), ("中文", "zh"), ("English", "en"),
                     ("日本語", "ja"), ("한국어", "ko")]
        for name, code in src_langs:
            self.src_lang.addItem(name, code)
        src_idx = self.src_lang.findData(config.get("language") or "auto")
        if src_idx >= 0:
            self.src_lang.setCurrentIndex(src_idx)
        row2b.addWidget(self.src_lang)
        row2b.addStretch()
        c2.addLayout(row2b)

        hint2 = QLabel("模型越大，识别越准确，但速度越慢、占用内存越多。\n建议：配置好的电脑用 large-v3，一般电脑用 base。")
        hint2.setObjectName("hint")
        hint2.setWordWrap(True)
        c2.addWidget(hint2)

        layout.addWidget(card2)

        # ── AI 模型设置 ──
        card3 = _make_card()
        c3 = QVBoxLayout(card3)
        c3.setSpacing(12)
        c3.setContentsMargins(24, 20, 24, 20)

        c3_title = QLabel("AI 模型")
        c3_title.setStyleSheet("color: #fff; font-size: 15px; font-weight: bold;")
        c3.addWidget(c3_title)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("当前模型："))
        self.model_input = QLineEdit(config["llm_model"])
        self.model_input.setPlaceholderText("例如: gemma4:26b, qwen2.5:1.5b")
        row3.addWidget(self.model_input)
        row3.addStretch()
        c3.addLayout(row3)

        hint3 = QLabel("这是本地 AI 大模型的名称（通过 Ollama 运行）。\n一般不需要修改，除非你想换一个模型。")
        hint3.setObjectName("hint")
        hint3.setWordWrap(True)
        c3.addWidget(hint3)

        layout.addWidget(card3)

        # ── 行为设置 ──
        card4 = _make_card()
        c4 = QVBoxLayout(card4)
        c4.setSpacing(12)
        c4.setContentsMargins(24, 20, 24, 20)

        c4_title = QLabel("行为设置")
        c4_title.setStyleSheet("color: #fff; font-size: 15px; font-weight: bold;")
        c4.addWidget(c4_title)

        self.auto_paste_cb = QCheckBox("识别完成后自动复制到剪贴板")
        self.auto_paste_cb.setChecked(config.get("auto_paste", True))
        c4.addWidget(self.auto_paste_cb)

        self.auto_start_cb = QCheckBox("开机自动启动 VoiceType")
        self.auto_start_cb.setChecked(config.get("auto_start", False))
        c4.addWidget(self.auto_start_cb)

        layout.addWidget(card4)

        # 保存
        layout.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedHeight(44)
        self.save_btn.setMinimumWidth(160)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

        scroll.setWidget(scroll_widget)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _save(self):
        self.config["translate_target"] = self.lang_combo.currentData()
        self.config["whisper_model"] = self.whisper_combo.currentData()
        src = self.src_lang.currentData()
        self.config["language"] = None if src == "auto" else src
        self.config["llm_model"] = self.model_input.text().strip()
        self.config["auto_paste"] = self.auto_paste_cb.isChecked()
        self.config["auto_start"] = self.auto_start_cb.isChecked()
        save_config(self.config)
        self.save_btn.setText("已保存!")
        QTimer.singleShot(1500, lambda: self.save_btn.setText("保存设置"))


# ─── 主窗口 ────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, config, signals):
        super().__init__()
        self.config = config
        self.signals = signals
        self.setWindowTitle("VoiceType 语音助手")
        self.setMinimumSize(900, 620)
        self.resize(960, 660)

        # 中央
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 侧边栏 ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 20, 10, 20)
        sb_layout.setSpacing(4)

        # Logo
        logo = QLabel("VoiceType")
        logo.setStyleSheet("color: #ffffff; font-size: 17px; font-weight: bold; padding: 10px 8px 20px 8px;")
        sb_layout.addWidget(logo)

        self.nav_buttons = []
        nav_items = [
            ("  首页", "home"),
            ("  快捷键设置", "hotkeys"),
            ("  其他设置", "settings"),
        ]
        for text, name in nav_items:
            btn = QPushButton(text)
            btn.setProperty("nav", name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._switch_page(n))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # 版本信息
        ver = QLabel(f"v1.0.0  ·  {EDITION}")
        ver.setStyleSheet("color: #44445a; font-size: 11px; padding: 8px;")
        sb_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # ── 内容区 ──
        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.home_page = HomePage(config, signals)
        self.hotkey_page = HotkeyPage(config)
        self.settings_page = SettingsPage(config)

        self.stack.addWidget(self.home_page)      # 0
        self.stack.addWidget(self.hotkey_page)     # 1
        self.stack.addWidget(self.settings_page)   # 2

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content, 1)

        self._switch_page("home")

    def _switch_page(self, name):
        page_map = {"home": 0, "hotkeys": 1, "settings": 2}
        self.stack.setCurrentIndex(page_map.get(name, 0))
        for btn in self.nav_buttons:
            btn.setProperty("active", "true" if btn.property("nav") == name else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def closeEvent(self, event):
        """关闭窗口 = 最小化到托盘，不退出"""
        event.ignore()
        self.hide()


# ─── 主应用 ────────────────────────────────────────────
class VoiceTypeApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("VoiceType")
        self.app.setStyleSheet(STYLE)

        self.config = load_config()
        self.engine = VoiceTypeEngine(self.config)
        self.signals = SignalBridge()
        self.hotkeys = HotkeyManager()
        self._current_mode = None
        self._last_toggle_time = 0

        # 创建主窗口
        self.main_window = MainWindow(self.config, self.signals)

        # 快捷键保存后自动热重载
        self.main_window.hotkey_page.hotkeys_saved.connect(self._reload_hotkeys)

        # 创建系统托盘
        self._create_tray()

        # 悬浮栏
        self.floating_bar = FloatingBar()

        # 连接信号
        self.signals.status_signal.connect(self.floating_bar.set_status)
        self.signals.result_signal.connect(self._show_result)
        self.signals.recording_started.connect(self.floating_bar.start_recording)
        self.signals.recording_stopped.connect(self.floating_bar.stop_recording)
        self.signals.error_signal.connect(self._show_error)

        self.engine.set_callbacks(
            on_status=lambda msg: self.signals.status_signal.emit(msg),
        )

        self._register_hotkeys()

    def _create_tray(self):
        self.tray = QSystemTrayIcon()

        # 图标
        px = QPixmap(32, 32)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 32, 32)
        grad.setColorAt(0, QColor(99, 102, 241))
        grad.setColorAt(1, QColor(139, 92, 246))
        path = QPainterPath()
        path.addRoundedRect(0, 0, 32, 32, 8, 8)
        p.fillPath(path, grad)
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("Arial", 17, QFont.Weight.Bold))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "V")
        p.end()
        self.tray.setIcon(QIcon(px))
        self.tray.setToolTip("VoiceType 语音助手 - 运行中")

        # 双击托盘图标打开主窗口
        self.tray.activated.connect(self._tray_activated)

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #1e1e2a; color: #c0c0d0; border: 1px solid #2a2a35; padding: 4px; }"
            "QMenu::item { padding: 8px 20px; border-radius: 4px; }"
            "QMenu::item:selected { background: #6366f1; color: white; }"
        )

        act_open = QAction("打开主界面", menu)
        act_open.triggered.connect(self._show_main)
        menu.addAction(act_open)
        menu.addSeparator()

        act_transcribe = QAction(f"语音整理  [{self.config['hotkey_transcribe'].upper()}]", menu)
        act_transcribe.triggered.connect(lambda: self._start_mode(VoiceMode.TRANSCRIBE))
        menu.addAction(act_transcribe)

        act_translate = QAction(f"语音翻译  [{self.config['hotkey_translate'].upper()}]", menu)
        act_translate.triggered.connect(lambda: self._start_mode(VoiceMode.TRANSLATE))
        menu.addAction(act_translate)

        act_assistant = QAction(f"AI 改写  [{self.config['hotkey_assistant'].upper()}]", menu)
        act_assistant.triggered.connect(lambda: self._start_mode(VoiceMode.REWRITE))
        menu.addAction(act_assistant)

        menu.addSeparator()
        act_quit = QAction("退出 VoiceType", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main()

    def _show_main(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _register_hotkeys(self):
        self.hotkeys.unregister_all()
        # Toggle 模式：按一下开始录音，再按一下停止并处理
        for key_name, mode in [
            ("hotkey_transcribe", VoiceMode.TRANSCRIBE),
            ("hotkey_translate", VoiceMode.TRANSLATE),
            ("hotkey_assistant", VoiceMode.REWRITE),
        ]:
            combo = self.config.get(key_name, "")
            if combo:
                self.hotkeys.register(
                    combo,
                    on_press=lambda m=mode: self._on_toggle(m),
                    on_release=None,  # toggle 模式不用 release
                )
        self.hotkeys.start()

    def _reload_hotkeys(self):
        self.config = load_config()
        self.hotkeys.stop()
        self._register_hotkeys()

    MODE_NAMES = {
        VoiceMode.TRANSCRIBE: "语音整理",
        VoiceMode.TRANSLATE: "语音翻译",
        VoiceMode.REWRITE: "AI 改写",
    }

    def _on_toggle(self, mode):
        """Toggle 模式：按一下开始录音，再按一下停止并处理"""
        import time as _time

        # 防抖：防止快速连按
        now = _time.time()
        if now - self._last_toggle_time < 0.5:
            return
        self._last_toggle_time = now

        if self.engine.recorder.is_recording:
            # 第二次按 → 停止录音并处理
            self.signals.recording_stopped.emit()
            current_mode = self._current_mode
            self._current_mode = None

            # 生成新任务ID，之前的旧任务自动失效
            task_id = self.engine.new_task_id()

            def process():
                try:
                    kwargs = {}
                    if current_mode == VoiceMode.TRANSLATE:
                        kwargs["target_lang"] = self.config["translate_target"]
                    elif current_mode == VoiceMode.REWRITE:
                        kwargs["selected_text"] = self._selected_text or ""
                    result = self.engine.stop_and_process(
                        current_mode, task_id=task_id, **kwargs)
                    if not self.engine.is_task_valid(task_id):
                        return  # 已被新录音取代，丢弃结果
                    if result:
                        self.signals.result_signal.emit(result, self.MODE_NAMES.get(current_mode, ""))
                    else:
                        self.signals.error_signal.emit("未识别到内容")
                except Exception as e:
                    if self.engine.is_task_valid(task_id):
                        self.signals.error_signal.emit(str(e))

            threading.Thread(target=process, daemon=True).start()
        else:
            # 第一次按 → 取消旧任务 + 开始新录音
            self.engine.new_task_id()  # 让之前可能还在处理的任务失效
            self._current_mode = mode
            self._selected_text = ""

            # 等待快捷键按键事件传递完毕
            _time.sleep(0.15)

            # AI改写模式：先获取选中的文字
            if mode == VoiceMode.REWRITE:
                try:
                    self._selected_text = self.engine.get_selected_text()
                    if self._selected_text:
                        self.signals.recording_started.emit(
                            f"AI 改写 (已获取 {len(self._selected_text)} 字)")
                    else:
                        self.signals.recording_started.emit("AI 改写 (未选中文字)")
                except Exception:
                    pass
                if not self._selected_text:
                    self.signals.recording_started.emit("AI 改写")
            else:
                self.signals.recording_started.emit(self.MODE_NAMES[mode])

            try:
                self.engine.start_recording()
            except Exception as e:
                self.signals.error_signal.emit(str(e))

    def _start_mode(self, mode):
        """从托盘菜单触发"""
        self._on_toggle(mode)

    def _show_result(self, text, mode_name):
        self.floating_bar.show_result(text)

    def _show_error(self, msg):
        self.floating_bar.set_status(f"出错: {msg}", "")
        QTimer.singleShot(5000, self.floating_bar.hide)

    def _quit(self):
        self.hotkeys.stop()
        self.engine.cleanup()
        self.tray.hide()
        self.app.quit()

    def run(self):
        # 打赏弹窗
        if should_show_donation():
            DonationDialog().exec()

        # 显示主窗口
        self.main_window.show()

        # 后台初始化引擎
        def init():
            try:
                self.engine.ensure_ready()
                self.signals.init_done.emit(True, "所有组件就绪，可以使用了!")
            except Exception as e:
                self.signals.init_done.emit(False, f"初始化失败: {e}")

        threading.Thread(target=init, daemon=True).start()

        self.tray.showMessage(
            "VoiceType 已启动",
            "语音助手在后台运行中。\n关闭窗口 = 最小化到托盘，不会退出。",
            QSystemTrayIcon.MessageIcon.Information, 3000,
        )

        return self.app.exec()


def run_gui():
    app = VoiceTypeApp()
    sys.exit(app.run())


if __name__ == "__main__":
    run_gui()
