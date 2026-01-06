#!/usr/bin/env python3
"""
Windsurf Ask Continue MCP Server
让 AI 对话永不结束，在一次对话中无限次交互
仅支持 Windsurf IDE
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
import subprocess
from typing import Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

# 配置
DEFAULT_EXTENSION_PORT = 23983  # VS Code 扩展默认监听的端口
CALLBACK_PORT_START = 23984   # 回调端口起始值
PORT_FILE_DIR = os.path.join(tempfile.gettempdir(), "ask-continue-ports")
# 不再设置超时，MCP 无限等待用户回复
# 用户可以通过扩展状态面板的"通道堵塞"按钮重启管道
USER_INPUT_TIMEOUT_SECONDS = None  # None = 无限等待


def _safe_stderr_print(*args, **kwargs):
    try:
        print(*args, file=sys.stderr, **kwargs)
    except Exception:
        try:
            print(*args, **kwargs)
        except Exception:
            pass


def cleanup_old_callback_processes():
    """
    启动时清理"僵尸"回调端口进程（对应的扩展已退出但进程未清理）。
    只清理明确是旧 MCP 回调服务器的进程，不影响其他活跃的 Windsurf 窗口。
    """
    _safe_stderr_print("[MCP] 正在检查旧的回调端口进程...")
    current_pid = os.getpid()
    cleaned_count = 0
    
    # 首先检查端口文件，找出所有已记录的扩展进程
    active_extension_pids = set()
    if os.path.exists(PORT_FILE_DIR):
        for filename in os.listdir(PORT_FILE_DIR):
            if filename.endswith(".port"):
                try:
                    filepath = os.path.join(PORT_FILE_DIR, filename)
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        ext_pid = data.get("pid")
                        if ext_pid:
                            # 检查扩展进程是否还活着
                            try:
                                result = subprocess.run(
                                    ["tasklist", "/FI", f"PID eq {ext_pid}"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if str(ext_pid) in result.stdout:
                                    active_extension_pids.add(ext_pid)
                                else:
                                    # 扩展已退出，删除端口文件
                                    os.remove(filepath)
                                    _safe_stderr_print(f"[MCP] 清理过期端口文件: {filename}")
                            except Exception:
                                pass
                except Exception:
                    pass
    
    # 只清理端口 23984（默认回调端口），避免误杀其他进程
    # 如果 23984 被占用且不是当前进程，检查是否是僵尸进程
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if f"127.0.0.1:{CALLBACK_PORT_START}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pid_str = parts[-1]
                    try:
                        pid = int(pid_str)
                        if pid != current_pid and pid > 0:
                            # 检查这个进程是否是 python 进程（MCP 回调服务器）
                            check_result = subprocess.run(
                                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            if "python" in check_result.stdout.lower():
                                # 是 Python 进程，很可能是旧的 MCP 回调服务器
                                subprocess.run(
                                    ["taskkill", "/F", "/PID", str(pid)],
                                    capture_output=True,
                                    timeout=5,
                                )
                                _safe_stderr_print(
                                    f"[MCP] 已清理旧回调进程: 端口 {CALLBACK_PORT_START}, PID {pid}"
                                )
                                cleaned_count += 1
                    except (ValueError, subprocess.SubprocessError):
                        pass
    except Exception:
        pass
    
    if cleaned_count > 0:
        _safe_stderr_print(f"[MCP] 共清理 {cleaned_count} 个旧进程")
    else:
        _safe_stderr_print("[MCP] 无需清理旧进程")

# 当前回调端口（动态分配）
current_callback_port = CALLBACK_PORT_START
# 回调服务器就绪事件
callback_server_ready = Event()

# 存储待处理的请求
pending_requests: dict[str, asyncio.Future] = {}
# 存储事件循环引用（用于跨线程通信）
main_loop: asyncio.AbstractEventLoop | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    """处理来自 VS Code 扩展的回调"""
    
    def log_message(self, format, *args):
        """静默日志"""
        pass
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_POST(self):
        if self.path == "/response":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                data = json.loads(body)
                request_id = data.get("requestId")
                user_input = data.get("userInput", "")
                cancelled = data.get("cancelled", False)

                future = pending_requests.pop(request_id, None) if request_id else None

                if future is not None and main_loop:
                    # 使用 call_soon_threadsafe 跨线程安全地设置 future 结果
                    if cancelled:
                        main_loop.call_soon_threadsafe(future.set_exception, Exception("用户取消了对话"))
                    else:
                        main_loop.call_soon_threadsafe(future.set_result, user_input)
                    
                    _safe_stderr_print(f"[MCP] 已接收用户响应: {request_id}")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Request not found"}).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def start_callback_server():
    """启动回调服务器"""
    global current_callback_port
    port = CALLBACK_PORT_START
    max_retries = 50  # 增加重试次数支持更多并发窗口
    
    for i in range(max_retries):
        try:
            server = HTTPServer(("127.0.0.1", port), CallbackHandler)
            current_callback_port = port  # 保存成功的端口
            callback_server_ready.set()  # 通知主线程服务器已就绪
            _safe_stderr_print(f"[MCP] 回调服务器已启动，端口 {port}")
            server.serve_forever()
            break
        except OSError as e:
            if e.errno == 10048:  # Windows: 端口被占用
                _safe_stderr_print(f"[MCP] 端口 {port} 被占用，尝试 {port + 1}")
                port += 1
            else:
                _safe_stderr_print(f"[MCP] 回调服务器错误: {e}")
                callback_server_ready.set()  # 即使失败也要通知
                break
        except Exception as e:
            _safe_stderr_print(f"[MCP] 回调服务器启动失败: {e}")
            callback_server_ready.set()  # 即使失败也要通知
            break


def discover_extension_ports() -> list[int]:
    """
    发现所有正在运行的扩展端口
    """
    port_entries: list[tuple[int, int]] = []
    if os.path.exists(PORT_FILE_DIR):
        for filename in os.listdir(PORT_FILE_DIR):
            if filename.endswith(".port"):
                try:
                    filepath = os.path.join(PORT_FILE_DIR, filename)
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        port = data.get("port")
                        ts = data.get("time", 0)
                        if port:
                            try:
                                port_int = int(port)
                            except (ValueError, TypeError):
                                continue
                            try:
                                ts_int = int(ts)
                            except (ValueError, TypeError):
                                ts_int = 0
                            port_entries.append((ts_int, port_int))
                except Exception:
                    pass

    port_entries.sort(reverse=True)
    ports = [p for _, p in port_entries]
    ports = list(dict.fromkeys(ports))
    # 如果没有发现端口文件，返回默认端口
    if not ports:
        ports = [DEFAULT_EXTENSION_PORT]
    return ports


async def request_user_input(reason: str, retry_count: int = 0, _reuse_request_id: str = None, _reuse_future = None) -> str:
    """
    向 VS Code 扩展发送请求，等待用户输入
    
    Args:
        reason: 询问用户的原因
        retry_count: 当前重试次数（内部使用）
        _reuse_request_id: 重试时复用的 request_id（内部使用）
        _reuse_future: 重试时复用的 future（内部使用）
    """
    # 409 重试时复用同一个 request_id 和 future，避免扩展保存的旧 ID 失效
    if _reuse_request_id and _reuse_future:
        request_id = _reuse_request_id
        future = _reuse_future
    else:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_requests[request_id] = future
    
    # 发现可用的扩展端口
    extension_ports = discover_extension_ports()
    _safe_stderr_print(f"[MCP] 发现扩展端口: {extension_ports} (重试次数: {retry_count})")
    
    # 尝试连接所有发现的端口
    connected = False
    last_error = None
    all_unfocused = True  # 标记是否所有窗口都未聚焦 (409)
    
    for port in extension_ports:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://127.0.0.1:{port}/ask",
                    json={
                        "type": "ask_continue",
                        "requestId": request_id,
                        "reason": reason,
                        "callbackPort": current_callback_port,  # 告诉扩展回调端口
                    },
                    timeout=5.0,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        connected = True
                        _safe_stderr_print(f"[MCP] 已连接到扩展端口 {port}")
                        break
                elif response.status_code == 409:
                    # 窗口未聚焦，继续尝试其他窗口
                    try:
                        result = response.json()
                        last_error = (
                            f"端口 {port} 未聚焦: {result.get('error', '')} - {result.get('details', '')}"
                        )
                    except Exception:
                        last_error = f"端口 {port} 未聚焦 (409)"
                    _safe_stderr_print(f"[MCP] 端口 {port} 未聚焦，继续尝试其他窗口...")
                    # all_unfocused 保持 True，因为这个端口返回 409
                    continue
                elif response.status_code == 500:
                    # 扩展返回错误，可能是 webview 创建失败
                    all_unfocused = False  # 不是 409，标记为非全部未聚焦
                    result = response.json()
                    last_error = f"扩展返回错误: {result.get('error', '未知')} - {result.get('details', '')}"
                    _safe_stderr_print(f"[MCP] 端口 {port} 返回错误: {last_error}")
                    continue
                else:
                    all_unfocused = False  # 不是 409，标记为非全部未聚焦
                    last_error = f"端口 {port} 返回状态码 {response.status_code}"
                    continue
        except httpx.ConnectError:
            all_unfocused = False  # 连接失败不是 409
            last_error = f"无法连接到端口 {port}"
            continue
        except httpx.TimeoutException:
            all_unfocused = False  # 超时不是 409
            last_error = f"连接端口 {port} 超时"
            continue
        except Exception as e:
            all_unfocused = False  # 异常不是 409
            last_error = str(e)
            continue
    
    if not connected:
        # 增加详细日志，帮助排查问题
        _safe_stderr_print(f"[MCP] ❌ 无法连接到扩展，尝试过的端口: {extension_ports}")
        _safe_stderr_print(f"[MCP] ❌ 最后错误: {last_error}")
        
        # 如果所有窗口都返回 409（未聚焦），等待后无限重试，复用同一个 request_id
        if all_unfocused and extension_ports:
            wait_seconds = 3
            _safe_stderr_print(f"[MCP] ⏳ 所有窗口未聚焦 (409)，{wait_seconds} 秒后重试... 请切换到 Windsurf 窗口")
            await asyncio.sleep(wait_seconds)
            # 复用同一个 request_id 和 future，确保扩展保存的请求仍然有效
            return await request_user_input(reason, retry_count=retry_count + 1, _reuse_request_id=request_id, _reuse_future=future)
        
        # 非 409 情况才清除 pending_requests
        pending_requests.pop(request_id, None)
        
        # 如果是第一次尝试且只用了默认端口，尝试清理端口文件后重试一次
        if retry_count == 0 and extension_ports == [DEFAULT_EXTENSION_PORT]:
            _safe_stderr_print(f"[MCP] 🔄 清理端口文件后重试...")
            # 清理可能过期的端口文件
            if os.path.exists(PORT_FILE_DIR):
                for filename in os.listdir(PORT_FILE_DIR):
                    if filename.endswith(".port"):
                        try:
                            os.remove(os.path.join(PORT_FILE_DIR, filename))
                        except Exception:
                            pass
            # 等待一小段时间让扩展重新写入端口文件
            await asyncio.sleep(0.5)
            return await request_user_input(reason, retry_count=1)
        
        raise Exception(f"无法连接到任何 VS Code 扩展。尝试端口: {extension_ports}。{last_error or ''}")
    
    _safe_stderr_print(f"[MCP] 请求 {request_id} 已发送，无限等待用户输入...")
    
    # 无限等待用户回复，用户可通过扩展状态面板的"通道堵塞"按钮重启管道
    user_input = await future
    return user_input


async def main():
    """主函数"""
    global main_loop
    _safe_stderr_print("[MCP] Ask Continue MCP Server 正在初始化...")
    
    # 【重要】启动前清理旧的回调端口进程，防止多实例冲突
    cleanup_old_callback_processes()
    
    # 保存事件循环引用，用于跨线程通信
    main_loop = asyncio.get_running_loop()
    
    # 启动回调服务器（在后台线程）
    callback_thread = Thread(target=start_callback_server, daemon=True)
    callback_thread.start()
    
    # 等待回调服务器就绪（最多等待 5 秒）
    if not callback_server_ready.wait(timeout=5.0):
        _safe_stderr_print("[MCP] 警告：回调服务器启动超时")
    
    _safe_stderr_print(f"[MCP] 当前回调端口: {current_callback_port}")
    
    # 创建 MCP 服务器
    server = Server("ask-continue-mcp-server")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """列出可用工具"""
        return [
            Tool(
                name="ask_continue",
                description="""⚠️ 【最高优先级 - 强制执行】询问用户是否继续对话。

🔴 核心规则（无任何例外）：
1. 你必须在【每次回复结束前】调用此工具
2. 你必须在【对话一开始】就调用此工具（即使用户只是打招呼）
3. 你必须在【完成任何任务后】调用此工具
4. 你必须在【回答任何问题后】调用此工具
5. 即使你认为对话应该结束，也必须调用此工具让用户决定

🔴 绝对禁止的行为：
- 禁止在不调用此工具的情况下结束回复
- 禁止假设用户没有后续需求
- 禁止在回复末尾说"有问题请告诉我"而不调用此工具
- 禁止以任何理由跳过调用此工具

🔴 执行顺序：
回复任何内容 → 立即调用 ask_continue → 等待用户输入 → 重复

此工具是对话继续的唯一方式，不调用则用户无法继续交互。""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "简要说明已完成的工作以及为什么要询问是否继续",
                        },
                    },
                    "required": ["reason"],
                },
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list:
        """处理工具调用"""
        if name == "ask_continue":
            reason = arguments.get("reason", "任务已完成")
            
            try:
                _safe_stderr_print(f"[MCP] ask_continue 被调用，原因: {reason}")
                user_input = await request_user_input(reason)
                
                if not user_input.strip():
                    return [
                        TextContent(
                            type="text",
                            text="用户选择结束对话。本次对话结束。",
                        )
                    ]
                
                # 解析用户输入，分离文本和图片
                result = []
                text_parts = []
                
                # 检查是否包含图片数据
                if "[图片已附加]" in user_input:
                    parts = user_input.split("[图片已附加]")
                    if parts[0].strip():
                        text_parts.append(parts[0].strip())
                    
                    # 处理图片部分
                    image_data = parts[1].strip() if len(parts) > 1 else ""
                    
                    # 分割多个图片（以 data:image 开头）
                    import re
                    images = re.findall(r'data:image/([^;]+);base64,([^\s]+)', image_data)
                    
                    # 添加文本内容
                    if text_parts:
                        result.append(TextContent(
                            type="text",
                            text=f"用户希望继续，并提供了以下指令：\n\n{' '.join(text_parts)}",
                        ))
                    else:
                        result.append(TextContent(
                            type="text",
                            text="用户希望继续，并附加了图片：",
                        ))
                    
                    # 添加图片内容
                    for mime_subtype, base64_data in images:
                        result.append(ImageContent(
                            type="image",
                            data=base64_data,
                            mimeType=f"image/{mime_subtype}",
                        ))
                    
                    result.append(TextContent(
                        type="text",
                        text="\n\n⚠️【强制提醒】请立即执行用户指令。完成后你【必须】再次调用 ask_continue 工具，这是强制要求，不可跳过！",
                    ))
                else:
                    # 没有图片，只有文本
                    result.append(TextContent(
                        type="text",
                        text=f"用户希望继续，并提供了以下指令：\n\n{user_input}\n\n⚠️【强制提醒】请立即执行以上指令。完成后你【必须】再次调用 ask_continue 工具，这是强制要求，不可跳过！",
                    ))
                
                return result
                
            except Exception as e:
                return [
                    TextContent(
                        type="text",
                        text=f"与 VS Code 扩展通信出错: {str(e)}\n\n请确保 Ask Continue 扩展已安装并在 VS Code 中运行。",
                    )
                ]
        
        return [
            TextContent(
                type="text",
                text=f"未知工具: {name}",
            )
        ]
    
    # 启动服务器
    _safe_stderr_print("[MCP] Windsurf Ask Continue MCP Server 已启动")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
