@echo off
chcp 65001 >nul
title Ask Continue - 卸载

echo ============================================
echo    Ask Continue - 卸载脚本
echo ============================================
echo.

:: 卸载 VS Code 扩展
echo [1/2] 卸载 VS Code 扩展...
code --uninstall-extension niumaMCP.ask-continue >nul 2>&1
echo [OK] 已尝试卸载扩展

:: 删除 MCP 配置
echo.
echo [2/2] 清理 MCP 配置...
set "WINDSURF_MCP_FILE=%USERPROFILE%\.codeium\windsurf\mcp_config.json"
if exist "%WINDSURF_MCP_FILE%" (
    del "%WINDSURF_MCP_FILE%"
    echo [OK] MCP 配置已删除
) else (
    echo [跳过] MCP 配置文件不存在
)

echo.
echo ============================================
echo    卸载完成！
echo ============================================
echo.
pause
