"""音频录制模块 - 支持静音检测"""
import io
import wave
import threading
import numpy as np

try:
    import pyaudio
except ImportError:
    pyaudio = None

from voicetype.core.config import load_config


class AudioRecorder:
    """麦克风录音器 - 带静音检测"""

    # 静音检测参数（仅用于判断是否有人声，不自动停止）
    SILENCE_THRESHOLD = 300      # 音量低于此值视为静音 (16bit PCM RMS)

    def __init__(self):
        self.config = load_config()
        self.sample_rate = self.config["sample_rate"]
        self.channels = self.config["channels"]
        self.chunk_size = 1024
        self.format = pyaudio.paInt16 if pyaudio else None
        self.is_recording = False
        self.frames = []
        self._pa = None
        self._stream = None
        self._thread = None
        self._had_voice = False       # 是否检测到过人声

    def _ensure_pyaudio(self):
        if pyaudio is None:
            raise RuntimeError("PyAudio 未安装。请运行: pip install pyaudio")
        if self._pa is None:
            self._pa = pyaudio.PyAudio()

    def list_devices(self) -> list[dict]:
        self._ensure_pyaudio()
        devices = []
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({
                    "index": i,
                    "name": info["name"],
                    "channels": info["maxInputChannels"],
                    "sample_rate": int(info["defaultSampleRate"]),
                })
        return devices

    def start(self, on_auto_stop=None):
        """开始录音"""
        self._ensure_pyaudio()
        self.frames = []
        self.is_recording = True
        self._had_voice = False
        self._stream = self._pa.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def _record_loop(self):
        while self.is_recording:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                self.frames.append(data)

                # 检测是否有人声（用于后续判断是否需要处理）
                samples = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(float) ** 2))
                if rms > self.SILENCE_THRESHOLD:
                    self._had_voice = True

            except Exception:
                break

    def stop(self) -> bytes:
        """停止录音，返回 WAV 格式的 bytes"""
        self.is_recording = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if not self.frames:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(self.frames))
        return buf.getvalue()

    def has_voice(self) -> bool:
        """录音中是否检测到过人声"""
        return self._had_voice

    def get_duration(self) -> float:
        if not self.frames:
            return 0.0
        return len(self.frames) * self.chunk_size / self.sample_rate

    def get_level(self) -> float:
        if not self.frames:
            return 0.0
        last_frame = np.frombuffer(self.frames[-1], dtype=np.int16)
        rms = np.sqrt(np.mean(last_frame.astype(float) ** 2))
        return min(rms / 32768.0 * 10, 1.0)

    def cleanup(self):
        if self._pa:
            self._pa.terminate()
            self._pa = None


class CLIRecorder:
    """终端模式录音器 - 按 Enter 停止"""

    def __init__(self):
        self.recorder = AudioRecorder()

    def record_until_enter(self) -> bytes:
        print("正在录音... 按 Enter 停止")
        self.recorder.start()
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        return self.recorder.stop()

    def record_for_seconds(self, seconds: float) -> bytes:
        import time
        print(f"正在录音 {seconds} 秒...")
        self.recorder.start()
        time.sleep(seconds)
        return self.recorder.stop()
