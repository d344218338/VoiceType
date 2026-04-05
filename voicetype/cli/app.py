"""终端 CLI 模式 - 在终端直接调用语音功能"""
import argparse
import sys
import os

# Windows 终端中文编码修复
if sys.platform == "win32":
    os.system("")  # 启用 ANSI 转义
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def print_banner():
    print("""
╔══════════════════════════════════════════╗
║       🎙️  VoiceType - 语音助手          ║
║   语音整理 · 语音翻译 · AI助手          ║
╚══════════════════════════════════════════╝
    """)


def cmd_transcribe(args):
    """语音整理命令"""
    from voicetype.core.engine import VoiceTypeEngine, VoiceMode
    engine = VoiceTypeEngine()

    if not engine.ensure_ready():
        sys.exit(1)

    if args.file:
        print(f"📂 从文件识别: {args.file}")
        with open(args.file, "rb") as f:
            audio = f.read()
    else:
        from voicetype.core.recorder import CLIRecorder
        rec = CLIRecorder()
        if args.duration:
            audio = rec.record_for_seconds(args.duration)
        else:
            audio = rec.record_until_enter()

    result = engine.process_audio(audio, VoiceMode.TRANSCRIBE)
    print(f"\n{'='*50}")
    print(f"📝 整理结果:\n")
    print(result)
    print(f"{'='*50}")

    if args.copy:
        _copy_to_clipboard(result)
        print("📋 已复制到剪贴板")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"💾 已保存到 {args.output}")

    return result


def cmd_translate(args):
    """语音翻译命令"""
    from voicetype.core.engine import VoiceTypeEngine, VoiceMode
    engine = VoiceTypeEngine()

    if not engine.ensure_ready():
        sys.exit(1)

    if args.text:
        # 文字翻译模式
        from voicetype.core.llm import OllamaLLM
        from voicetype.core.config import load_config
        config = load_config()
        llm = OllamaLLM(model=config["llm_model"], base_url=config["ollama_url"])
        result = llm.translate(args.text, args.target)
    elif args.file:
        with open(args.file, "rb") as f:
            audio = f.read()
        result = engine.process_audio(audio, VoiceMode.TRANSLATE, target_lang=args.target)
    else:
        from voicetype.core.recorder import CLIRecorder
        rec = CLIRecorder()
        if args.duration:
            audio = rec.record_for_seconds(args.duration)
        else:
            audio = rec.record_until_enter()
        result = engine.process_audio(audio, VoiceMode.TRANSLATE, target_lang=args.target)

    print(f"\n{'='*50}")
    print(f"🌐 翻译结果 (→ {args.target}):\n")
    print(result)
    print(f"{'='*50}")

    if args.copy:
        _copy_to_clipboard(result)

    return result


def cmd_ask(args):
    """AI 助手命令"""
    from voicetype.core.engine import VoiceTypeEngine, VoiceMode
    engine = VoiceTypeEngine()

    if not engine.ensure_ready():
        sys.exit(1)

    if args.text:
        # 文字提问模式
        from voicetype.core.llm import OllamaLLM
        from voicetype.core.config import load_config
        config = load_config()
        llm = OllamaLLM(model=config["llm_model"], base_url=config["ollama_url"])
        result = llm.ask(args.text)
    else:
        from voicetype.core.recorder import CLIRecorder
        rec = CLIRecorder()
        if args.duration:
            audio = rec.record_for_seconds(args.duration)
        else:
            audio = rec.record_until_enter()
        result = engine.process_audio(audio, VoiceMode.ASSISTANT)

    print(f"\n{'='*50}")
    print(f"🤖 AI 回答:\n")
    print(result)
    print(f"{'='*50}")

    if args.copy:
        _copy_to_clipboard(result)

    return result


def cmd_chat(args):
    """交互式 AI 聊天"""
    from voicetype.core.llm import OllamaLLM
    from voicetype.core.config import load_config
    config = load_config()
    llm = OllamaLLM(model=config["llm_model"], base_url=config["ollama_url"])

    if not llm.ensure_ready():
        sys.exit(1)

    print_banner()
    print("💬 进入聊天模式 (输入 /quit 退出, /voice 语音输入)\n")

    messages = [{"role": "system", "content": "你是一个智能AI助手。简洁、准确地回答用户的问题。"}]

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("👋 再见!")
            break
        if user_input == "/voice":
            from voicetype.core.recorder import CLIRecorder
            from voicetype.core.stt import SpeechToText
            rec = CLIRecorder()
            audio = rec.record_until_enter()
            stt = SpeechToText(model_size=config["whisper_model"], device=config["whisper_device"])
            result = stt.transcribe(audio)
            user_input = result["text"]
            print(f"🎤 识别: {user_input}")
            if not user_input.strip():
                print("（未识别到语音）")
                continue

        messages.append({"role": "user", "content": user_input})
        response = llm.chat(messages, temperature=0.7)
        messages.append({"role": "assistant", "content": response})
        print(f"\nAI: {response}\n")


def cmd_config(args):
    """配置管理"""
    from voicetype.core.config import load_config, save_config, CONFIG_FILE

    config = load_config()

    if args.show:
        import json
        print(f"📁 配置文件: {CONFIG_FILE}")
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    if args.set:
        key, value = args.set.split("=", 1)
        key = key.strip()
        value = value.strip()
        # 尝试解析为合适的类型
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        config[key] = value
        save_config(config)
        print(f"✅ 已设置 {key} = {value}")

    if args.model:
        config["llm_model"] = args.model
        save_config(config)
        print(f"✅ LLM 模型已设为: {args.model}")

    if args.whisper:
        config["whisper_model"] = args.whisper
        save_config(config)
        print(f"✅ Whisper 模型已设为: {args.whisper}")

    if args.language:
        config["language"] = args.language if args.language != "auto" else None
        save_config(config)
        print(f"✅ 识别语言已设为: {args.language}")


def cmd_setup(args):
    """初始化设置 - 检查并下载所有依赖"""
    from voicetype.core.engine import VoiceTypeEngine
    print_banner()
    print("🔧 正在初始化 VoiceType...\n")
    engine = VoiceTypeEngine()
    if engine.ensure_ready():
        print("\n🎉 VoiceType 初始化完成! 你可以开始使用了。")
        print("\n常用命令:")
        print("  voicetype transcribe    语音整理")
        print("  voicetype translate     语音翻译")
        print("  voicetype ask           语音提问")
        print("  voicetype chat          交互式聊天")
        print("  voicetype gui           启动图形界面")
    else:
        print("\n❌ 初始化失败，请检查错误信息。")
        sys.exit(1)


def cmd_gui(args):
    """启动 GUI 模式"""
    from voicetype.gui.app import run_gui
    run_gui()


def _copy_to_clipboard(text: str):
    try:
        import subprocess
        process = subprocess.Popen(
            ["clip.exe"] if sys.platform == "win32" else ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
        )
        process.communicate(text.encode("utf-16-le" if sys.platform == "win32" else "utf-8"))
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        prog="voicetype",
        description="VoiceType - 免费本地语音助手",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # transcribe
    p_trans = subparsers.add_parser("transcribe", aliases=["t"], help="语音整理 - 录音并整理为书面文字")
    p_trans.add_argument("-f", "--file", help="从音频文件识别")
    p_trans.add_argument("-d", "--duration", type=float, help="录音时长（秒）")
    p_trans.add_argument("-c", "--copy", action="store_true", help="自动复制到剪贴板")
    p_trans.add_argument("-o", "--output", help="保存到文件")
    p_trans.set_defaults(func=cmd_transcribe)

    # translate
    p_tl = subparsers.add_parser("translate", aliases=["tl"], help="语音翻译 - 录音并翻译")
    p_tl.add_argument("-t", "--target", default="en", help="目标语言 (默认: en)")
    p_tl.add_argument("-f", "--file", help="从音频文件识别")
    p_tl.add_argument("-d", "--duration", type=float, help="录音时长（秒）")
    p_tl.add_argument("--text", help="直接翻译文字（不录音）")
    p_tl.add_argument("-c", "--copy", action="store_true", help="自动复制到剪贴板")
    p_tl.set_defaults(func=cmd_translate)

    # ask
    p_ask = subparsers.add_parser("ask", aliases=["a"], help="AI 助手 - 语音提问")
    p_ask.add_argument("-d", "--duration", type=float, help="录音时长（秒）")
    p_ask.add_argument("--text", help="直接文字提问（不录音）")
    p_ask.add_argument("-c", "--copy", action="store_true", help="自动复制到剪贴板")
    p_ask.set_defaults(func=cmd_ask)

    # chat
    p_chat = subparsers.add_parser("chat", help="交互式 AI 聊天")
    p_chat.set_defaults(func=cmd_chat)

    # config
    p_cfg = subparsers.add_parser("config", help="配置管理")
    p_cfg.add_argument("--show", action="store_true", help="显示当前配置")
    p_cfg.add_argument("--set", help="设置配置项 (key=value)")
    p_cfg.add_argument("--model", help="设置 LLM 模型")
    p_cfg.add_argument("--whisper", help="设置 Whisper 模型大小")
    p_cfg.add_argument("--language", help="设置识别语言 (auto=自动检测)")
    p_cfg.set_defaults(func=cmd_config)

    # setup
    p_setup = subparsers.add_parser("setup", help="初始化 - 下载模型和检查依赖")
    p_setup.set_defaults(func=cmd_setup)

    # gui
    p_gui = subparsers.add_parser("gui", help="启动图形界面")
    p_gui.set_defaults(func=cmd_gui)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
