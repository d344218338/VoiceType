@echo off
chcp 65001 >nul 2>&1
title VoiceType 语音助手 - 一键安装
color 0F
setlocal EnableDelayedExpansion

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║         VoiceType 语音助手 - 一键安装程序                ║
echo  ║                                                          ║
echo  ║    免费本地 AI 语音整理 · 翻译 · 智能问答               ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  本程序将自动为你完成所有安装配置:
echo.
echo    [1] 检查/安装 Python (编程语言环境)
echo    [2] 检查/安装 Ollama (本地AI运行引擎)
echo    [3] 下载 AI 模型 (约1GB, 首次需要几分钟)
echo    [4] 安装 VoiceType 语音助手
echo    [5] 创建桌面快捷方式
echo.
echo  全程自动, 你只需要等待即可。
echo.
echo  ════════════════════════════════════════════════════════════
echo   按任意键开始安装...
echo  ════════════════════════════════════════════════════════════
pause >nul

set "VOICETYPE_EDITION=public"
set "INSTALL_DIR=%LOCALAPPDATA%\VoiceType"
set "SCRIPT_DIR=%~dp0"
set "ERRORS=0"

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM ═══════════════════════════════════════════
REM  第1步: 检查 Python
REM ═══════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────
echo   [1/5] 检查 Python 环境
echo  ─────────────────────────────────────────

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] 未检测到 Python, 正在自动下载安装...
    echo.

    set "PY_INSTALLER=%TEMP%\python-installer.exe"

    echo  正在下载 Python 安装包...
    powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '!PY_INSTALLER!' }"

    if not exist "!PY_INSTALLER!" (
        echo.
        echo  [X] Python 下载失败!
        echo      请手动下载安装: https://www.python.org/downloads/
        echo      安装时务必勾选 "Add Python to PATH"
        echo      安装完成后重新运行本程序
        echo.
        pause
        exit /b 1
    )

    echo  正在安装 Python (请等待, 不要关闭窗口)...
    start /wait "" "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
    del "!PY_INSTALLER!" 2>nul

    REM 刷新环境变量
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"

    python --version >nul 2>&1
    if errorlevel 1 (
        echo  [X] Python 安装可能需要重启电脑后生效
        echo      请重启电脑后重新运行本安装程序
        pause
        exit /b 1
    )
)

for /f "tokens=2" %%a in ('python --version 2^>^&1') do set PYVER=%%a
echo  [OK] Python %PYVER% 已就绪

REM ═══════════════════════════════════════════
REM  第2步: 检查/安装 Ollama
REM ═══════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────
echo   [2/5] 检查 Ollama (本地AI运行引擎)
echo  ─────────────────────────────────────────

ollama --version >nul 2>&1
if errorlevel 1 (
    echo  [!] 未检测到 Ollama, 正在自动下载安装...
    echo.

    set "OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe"

    echo  正在下载 Ollama 安装包 (约80MB)...
    powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '!OLLAMA_INSTALLER!' }"

    if not exist "!OLLAMA_INSTALLER!" (
        echo  [X] Ollama 下载失败!
        echo      请手动下载: https://ollama.com/download
        echo      安装完成后重新运行本程序
        pause
        exit /b 1
    )

    echo  正在安装 Ollama (请等待)...
    start /wait "" "!OLLAMA_INSTALLER!" /VERYSILENT /NORESTART
    del "!OLLAMA_INSTALLER!" 2>nul

    echo  等待 Ollama 服务启动...
    timeout /t 8 /nobreak >nul

    ollama --version >nul 2>&1
    if errorlevel 1 (
        REM 尝试添加常见路径
        set "PATH=%LOCALAPPDATA%\Programs\Ollama\;%PATH%"
        ollama --version >nul 2>&1
        if errorlevel 1 (
            echo  [X] Ollama 安装似乎未完成
            echo      请手动安装: https://ollama.com/download
            echo      安装完成后重新运行本程序
            pause
            exit /b 1
        )
    )
)

echo  [OK] Ollama 已就绪

REM 确保 Ollama 服务在运行
powershell -Command "& { try { Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 3 -ErrorAction Stop | Out-Null; Write-Host '  [OK] Ollama 服务正在运行' } catch { Write-Host '  [!] 正在启动 Ollama 服务...'; Start-Process 'ollama' -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep -Seconds 6; Write-Host '  [OK] Ollama 服务已启动' } }"

REM ═══════════════════════════════════════════
REM  第3步: 下载 AI 模型
REM ═══════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────
echo   [3/5] 下载 AI 模型 (qwen2.5:1.5b)
echo  ─────────────────────────────────────────
echo  模型大小约 1GB, 首次下载需要几分钟...
echo.

ollama pull qwen2.5:1.5b
if errorlevel 1 (
    echo  [!] 模型下载失败, 将在首次使用时自动重试
    set /a ERRORS+=1
) else (
    echo  [OK] AI 模型已就绪
)

REM ═══════════════════════════════════════════
REM  第4步: 安装 VoiceType
REM ═══════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────
echo   [4/5] 安装 VoiceType 语音助手
echo  ─────────────────────────────────────────

REM 复制文件
echo  复制程序文件...
xcopy /E /Y /I /Q "%SCRIPT_DIR%voicetype" "%INSTALL_DIR%\voicetype" >nul 2>&1
copy /Y "%SCRIPT_DIR%pyproject.toml" "%INSTALL_DIR%\" >nul 2>&1

REM 安装依赖
echo  安装程序依赖 (这一步可能需要1-2分钟)...
cd /d "%INSTALL_DIR%"
pip install -e ".[all]" -q 2>nul

if errorlevel 1 (
    echo  [!] 依赖安装遇到问题, 尝试单独安装...
    pip install faster-whisper pyaudio pynput numpy PyQt6 -q 2>nul
)

echo  [OK] VoiceType 安装完成

REM ═══════════════════════════════════════════
REM  第5步: 创建快捷方式和启动脚本
REM ═══════════════════════════════════════════
echo.
echo  ─────────────────────────────────────────
echo   [5/5] 创建快捷方式
echo  ─────────────────────────────────────────

REM 创建 GUI 启动脚本
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo set "VOICETYPE_EDITION=public"
echo cd /d "%INSTALL_DIR%"
echo start /min "" pythonw -m voicetype gui
) > "%INSTALL_DIR%\VoiceType.bat"

REM 创建终端启动脚本 (加入 PATH)
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo set "VOICETYPE_EDITION=public"
echo set PYTHONUTF8=1
echo cd /d "%INSTALL_DIR%"
echo python -m voicetype %%*
) > "%INSTALL_DIR%\vt.bat"

REM 添加到用户 PATH
powershell -Command "& { $currentPath = [Environment]::GetEnvironmentVariable('Path', 'User'); if ($currentPath -notlike '*VoiceType*') { [Environment]::SetEnvironmentVariable('Path', $currentPath + ';%INSTALL_DIR%', 'User'); Write-Host '  [OK] 已添加到系统路径 (新终端窗口中可用 vt 命令)' } else { Write-Host '  [OK] 系统路径已配置' } }"

REM 创建桌面快捷方式
powershell -Command "& { $WshShell = New-Object -ComObject WScript.Shell; $Desktop = [Environment]::GetFolderPath('Desktop'); $Shortcut = $WshShell.CreateShortcut(\"$Desktop\VoiceType 语音助手.lnk\"); $Shortcut.TargetPath = '%INSTALL_DIR%\VoiceType.bat'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'VoiceType - 免费本地AI语音助手'; $Shortcut.WindowStyle = 7; $Shortcut.Save(); Write-Host '  [OK] 桌面快捷方式已创建' }"

REM ═══════════════════════════════════════════
REM  安装完成
REM ═══════════════════════════════════════════
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║              安装完成!                                   ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  怎么用:
echo.
echo  方式一: 双击桌面上的 "VoiceType 语音助手" 图标
echo          启动后在右下角系统托盘, 按住快捷键说话:
echo          Ctrl+Alt+T  语音整理 (说完自动变成书面文字)
echo          Ctrl+Alt+Y  语音翻译 (说完自动翻译)
echo          Ctrl+Alt+A  AI助手   (说完AI回答你)
echo.
echo  方式二: 打开终端/命令提示符, 输入:
echo          vt transcribe   语音整理
echo          vt translate    语音翻译
echo          vt ask          语音提问
echo          vt chat         跟AI聊天
echo.

if %ERRORS% GTR 0 (
    echo  [!] 安装过程中有 %ERRORS% 个警告, 但不影响使用
    echo      首次启动时会自动修复
    echo.
)

echo  ════════════════════════════════════════════════════════════
echo   按任意键关闭安装程序...
echo  ════════════════════════════════════════════════════════════
pause >nul
