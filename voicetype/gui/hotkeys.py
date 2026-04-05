"""全局快捷键模块 - 支持按住录音，支持左/右修饰键区分"""
import threading
import sys
from pynput import keyboard


class HotkeyManager:
    """全局快捷键管理器，支持"按住录音，松开处理"模式"""

    def __init__(self):
        self._bindings = {}  # frozenset -> {"on_press": fn, "on_release": fn}
        self._pressed_keys = set()
        self._active_combo = None
        self._listener = None

    def register(self, combo_str: str, on_press=None, on_release=None):
        keys = self._parse_combo(combo_str)
        self._bindings[frozenset(keys)] = {
            "on_press": on_press,
            "on_release": on_release,
            "combo_str": combo_str,
        }

    def unregister_all(self):
        self._bindings.clear()

    def _parse_combo(self, combo_str: str) -> set:
        """解析快捷键字符串，支持 ralt/lalt/rctrl/lctrl/rshift/lshift"""
        key_map = {
            # 左修饰键
            "ctrl": keyboard.Key.ctrl_l,
            "lctrl": keyboard.Key.ctrl_l,
            "alt": keyboard.Key.alt_l,
            "lalt": keyboard.Key.alt_l,
            "shift": keyboard.Key.shift_l,
            "lshift": keyboard.Key.shift_l,
            # 右修饰键
            "rctrl": keyboard.Key.ctrl_r,
            "ralt": "RALT",       # 特殊标记，运行时匹配 alt_r 或 alt_gr
            "rightalt": "RALT",
            "rshift": keyboard.Key.shift_r,
            # 其他
            "cmd": keyboard.Key.cmd,
            "win": keyboard.Key.cmd,
            "space": keyboard.Key.space,
            "enter": keyboard.Key.enter,
            "tab": keyboard.Key.tab,
            "esc": keyboard.Key.esc,
            "backspace": keyboard.Key.backspace,
            "delete": keyboard.Key.delete,
            "up": keyboard.Key.up, "down": keyboard.Key.down,
            "left": keyboard.Key.left, "right": keyboard.Key.right,
            "f1": keyboard.Key.f1, "f2": keyboard.Key.f2, "f3": keyboard.Key.f3,
            "f4": keyboard.Key.f4, "f5": keyboard.Key.f5, "f6": keyboard.Key.f6,
            "f7": keyboard.Key.f7, "f8": keyboard.Key.f8, "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10, "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
        }
        keys = set()
        for part in combo_str.lower().split("+"):
            part = part.strip()
            if not part:
                continue
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                try:
                    keys.add(getattr(keyboard.Key, part))
                except AttributeError:
                    if len(part) > 0:
                        keys.add(keyboard.KeyCode.from_char(part[0]))
        return keys

    def _normalize_key(self, key):
        """
        把右 Alt 的各种表示统一为 "RALT" 标记。
        Windows 上右 Alt 可能报告为 alt_r、alt_gr、或带 vk 的 KeyCode。
        """
        # pynput 在 Windows 上右 Alt 可能是 alt_gr
        if key == keyboard.Key.alt_r:
            return "RALT"
        if key == keyboard.Key.alt_gr:
            return "RALT"
        # 有些键盘驱动把右Alt报告为 vk=165 的 KeyCode
        if hasattr(key, "vk") and key.vk == 165:
            return "RALT"
        return key

    def _on_press(self, key):
        nkey = self._normalize_key(key)
        self._pressed_keys.add(nkey)

        if self._active_combo is not None:
            return

        # 优先匹配键数最多的组合（避免 ralt 单键抢先于 ralt+rshift）
        # 所以这里不立即触发，而是等一小段时间看看有没有更多的键按下
        # 但对于多键组合可以立即触发
        matched = []
        for combo, binding in self._bindings.items():
            if combo.issubset(self._pressed_keys):
                matched.append((combo, binding))

        if not matched:
            return

        # 选择键数最多的匹配
        matched.sort(key=lambda x: len(x[0]), reverse=True)
        best_combo, best_binding = matched[0]
        self._active_combo = best_combo
        if best_binding["on_press"]:
            threading.Thread(target=best_binding["on_press"], daemon=True).start()

    def _on_release(self, key):
        nkey = self._normalize_key(key)

        if self._active_combo is not None and nkey in self._active_combo:
            combo = self._active_combo
            binding = self._bindings.get(combo)
            self._active_combo = None
            if binding and binding["on_release"]:
                threading.Thread(target=binding["on_release"], daemon=True).start()

        self._pressed_keys.discard(nkey)

        # 单键快捷键的延迟触发逻辑：
        # 如果释放了某个键后，剩余按住的键刚好匹配一个单键组合，不触发
        # （因为用户是在松开多键组合的过程中）

    def start(self):
        if self._listener:
            self.stop()
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def restart_with_config(self, config: dict, press_callbacks: dict, release_callback):
        """用新配置重新注册所有快捷键并重启监听"""
        self.stop()
        self.unregister_all()
        for key, mode in press_callbacks.items():
            hotkey_str = config.get(key, "")
            if hotkey_str:
                self.register(
                    hotkey_str,
                    on_press=mode["on_press"],
                    on_release=release_callback,
                )
        self.start()
