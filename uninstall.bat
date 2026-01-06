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
    copy "%WINDSURF_MCP_FILE%" "%WINDSURF_MCP_FILE%.backup" >nul 2>&1
    echo [备份] 旧 MCP 配置已备份到: %WINDSURF_MCP_FILE%.backup

    python -c "import json,pathlib; p=pathlib.Path(r'%WINDSURF_MCP_FILE%'); t=p.read_text(encoding='utf-8') if p.exists() else ''; data=json.loads(t) if t.strip() else {}; data=data if isinstance(data,dict) else {}; m=data.get('mcpServers'); m=m if isinstance(m,dict) else {}; m.pop('ask-continue', None); data['mcpServers']=m; p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')"
    if errorlevel 1 (
        echo [错误] MCP 配置更新失败，正在尝试恢复备份...
        if exist "%WINDSURF_MCP_FILE%.backup" copy /Y "%WINDSURF_MCP_FILE%.backup" "%WINDSURF_MCP_FILE%" >nul 2>&1
        pause
        exit /b 1
    )

    echo [OK] 已从 MCP 配置中移除 ask-continue
) else (
    echo [跳过] MCP 配置文件不存在
)

echo.
echo ============================================
echo    卸载完成！
echo ============================================
echo.
pause
