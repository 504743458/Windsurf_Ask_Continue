@echo off
chcp 65001 >nul
title Ask Continue - 一键安装

:: 保存用户当前工作目录
set "USER_PROJECT_DIR=%CD%"

echo ============================================
echo    Ask Continue - 继续牛马 MCP 工具
echo    一键安装脚本
echo ============================================
echo.

:: 检查 Python
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已安装

:: 安装 Python 依赖
echo.
echo [2/5] 安装 MCP Server 依赖...
cd /d "%~dp0mcp-server-python"
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] Python 依赖安装失败
    pause
    exit /b 1
)
echo [OK] Python 依赖已安装

:: 配置 MCP
echo.
echo [3/5] 配置 MCP...

:: 获取当前目录路径（转换斜杠）
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:\=/%"
set "SERVER_PATH=%SCRIPT_DIR%mcp-server-python/server.py"

:: 正确的 Windsurf MCP 配置路径
set "WINDSURF_MCP_DIR=%USERPROFILE%\.codeium\windsurf"
set "WINDSURF_MCP_FILE=%WINDSURF_MCP_DIR%\mcp_config.json"

:: 创建目录（如果不存在）
if not exist "%WINDSURF_MCP_DIR%" mkdir "%WINDSURF_MCP_DIR%"

:: 写入 MCP 配置
echo {> "%WINDSURF_MCP_FILE%"
echo   "mcpServers": {>> "%WINDSURF_MCP_FILE%"
echo     "ask-continue": {>> "%WINDSURF_MCP_FILE%"
echo       "command": "python",>> "%WINDSURF_MCP_FILE%"
echo       "args": ["%SERVER_PATH%"]>> "%WINDSURF_MCP_FILE%"
echo     }>> "%WINDSURF_MCP_FILE%"
echo   }>> "%WINDSURF_MCP_FILE%"
echo }>> "%WINDSURF_MCP_FILE%"

echo [OK] MCP 配置已写入: %WINDSURF_MCP_FILE%

:: 安装 VS Code 扩展
echo.
echo [4/5] 安装 VS Code 扩展...
set "VSIX_FILE=%~dp0ask-continue-1.0.0.vsix"

echo [提示] 请手动安装扩展:
echo        1. 按 Ctrl+Shift+P
echo        2. 输入 Extensions: Install from VSIX
echo        3. 选择 VSIX 文件
echo.
echo 正在打开文件位置...
explorer /select,"%VSIX_FILE%"

:: 复制规则文件到用户全局目录
echo.
echo [5/5] 配置全局规则文件...
set "RULES_SRC=%~dp0rules\example-windsurfrules.txt"
set "RULES_DST=%USERPROFILE%\.windsurfrules"

if exist "%RULES_DST%" (
    echo [跳过] 全局 .windsurfrules 已存在: %RULES_DST%
) else (
    if exist "%RULES_SRC%" (
        copy "%RULES_SRC%" "%RULES_DST%" >nul
        echo [OK] 全局规则已创建: %RULES_DST%
    ) else (
        echo [警告] 规则模板文件不存在: %RULES_SRC%
    )
)

echo.
echo ============================================
echo    安装完成！
echo ============================================
echo.
echo 下一步:
echo   [1] 重启 Windsurf
echo   [2] 开始对话，AI 完成任务后会自动弹窗
echo.
echo 全局规则: %USERPROFILE%\.windsurfrules
echo MCP 配置: %USERPROFILE%\.codeium\windsurf\mcp_config.json
echo.
pause
