"""核心引擎 - 串联录音、识别、LLM处理的完整流程"""
import time
import threading
import pyperclip
import pyautogui
from enum import Enum
from voicetype.core.config import load_config
from voicetype.core.recorder import AudioRecorder
from voicetype.core.stt import SpeechToText
from voicetype.core.llm import OllamaLLM


class VoiceMode(Enum):
    TRANSCRIBE = "transcribe"   # 语音整理：说话→整理成书面文字→自动输入
    TRANSLATE = "translate"     # 语音翻译：说话→翻译→自动输入
    REWRITE = "rewrite"         # AI改写：选中文字→说指令→AI改写并替换


# pyautogui 安全设置
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class VoiceTypeEngine:
    """VoiceType 核心引擎"""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.recorder = AudioRecorder()
        self.stt = SpeechToText(
            model_size=self.config["whisper_model"],
            device=self.config["whisper_device"],
            language=self.config.get("language"),
        )
        self.llm = OllamaLLM(
            model=self.config["llm_model"],
            base_url=self.config["ollama_url"],
        )
        self._on_status = None
        self._on_result = None
        # 任务取消机制
        self._task_id = 0
        self._task_lock = threading.Lock()

    def new_task_id(self) -> int:
        """生成新任务ID，旧任务自动失效"""
        with self._task_lock:
            self._task_id += 1
            return self._task_id

    def is_task_valid(self, task_id: int) -> bool:
        """检查任务是否仍然有效（没被新任务取代）"""
        return task_id == self._task_id

    def set_callbacks(self, on_status=None, on_result=None):
        self._on_status = on_status
        self._on_result = on_result

    def _status(self, msg: str):
        if self._on_status:
            self._on_status(msg)

    def ensure_ready(self) -> bool:
        self._status("正在检查 Ollama...")
        if not self.llm.ensure_ready():
            return False
        self._status("所有组件就绪，可以使用了!")
        return True

    # ── 录音控制 ──
    def start_recording(self, on_auto_stop=None):
        self._status("正在录音...")
        self.recorder.start(on_auto_stop=on_auto_stop)

    def stop_recording(self) -> bytes:
        self._status("录音结束，处理中...")
        return self.recorder.stop()

    # ── 获取选中文字 ──
    def get_selected_text(self) -> str:
        """通过 Ctrl+C 获取当前选中的文字"""
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass

        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)

        try:
            selected = pyperclip.paste()
        except Exception:
            return ""

        if selected != old_clip:
            return selected
        return ""

    # ── 自动输入到当前窗口 ──
    def type_text(self, text: str):
        """把文字粘贴到当前活动窗口"""
        if not text.strip():
            return
        # 清理 markdown 格式符号
        text = text.replace("**", "").replace("__", "")
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")

    # ── 核心处理流程 ──
    def process_audio(self, audio_bytes: bytes, mode: VoiceMode, task_id: int = 0, **kwargs) -> str:
        if not audio_bytes or len(audio_bytes) < 1000:
            self._status("未检测到有效音频")
            return ""

        # 检查任务是否被取消
        if task_id and not self.is_task_valid(task_id):
            return ""

        # 1. 语音识别
        self._status("正在识别语音...")
        result = self.stt.transcribe(audio_bytes)
        raw_text = result["text"]

        if not raw_text.strip():
            self._status("未识别到语音")
            return ""

        # 再次检查取消
        if task_id and not self.is_task_valid(task_id):
            return ""

        self._status(f"识别到: {raw_text[:40]}...")

        # 2. 根据模式处理
        if mode == VoiceMode.TRANSCRIBE:
            self._status("正在整理文本...")
            final = self.llm.refine_text(raw_text)

        elif mode == VoiceMode.TRANSLATE:
            target_lang = kwargs.get("target_lang", self.config["translate_target"])
            self._status("正在翻译...")
            final = self.llm.translate(raw_text, target_lang)

        elif mode == VoiceMode.REWRITE:
            selected_text = kwargs.get("selected_text", "")
            if not selected_text:
                self._status("未获取到选中文字")
                return ""
            self._status("AI 正在改写...")
            final = self.llm.rewrite(selected_text, raw_text)

        else:
            final = raw_text

        # 最后检查取消
        if task_id and not self.is_task_valid(task_id):
            return ""

        # 清理 markdown 符号
        final = final.strip().replace("**", "").replace("__", "")
        return final

    def stop_and_process(self, mode: VoiceMode, task_id: int = 0, **kwargs) -> str:
        audio = self.stop_recording()

        # 检查是否有声音
        if not self.recorder.has_voice():
            self._status("未检测到语音")
            return ""

        result = self.process_audio(audio, mode, task_id=task_id, **kwargs)

        if result and self.is_task_valid(task_id):
            if self.config.get("auto_paste", True):
                self.type_text(result)
            if self._on_result:
                self._on_result(result)

        return result

    def cleanup(self):
        self.recorder.cleanup()
