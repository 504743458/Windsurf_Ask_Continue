# Windsurf Ask Continue - 无限对话 MCP 工具

> ⚠️ **仅支持 Windsurf IDE**，不支持 VS Code、Cursor 等其他编辑器。

让 AI 对话永不结束，在一次对话中无限次交互。

---

## 👤 作者

**Rhongomiant1227**

- 🔗 GitHub: [github.com/Rhongomiant1227](https://github.com/Rhongomiant1227)
- 📺 B站: [space.bilibili.com/21070946](https://space.bilibili.com/21070946)

如果觉得好用，欢迎 Star ⭐ 和关注！

---

## 💬 为什么开源这个？

> 有人把这玩意儿拿去闲鱼上卖钱了。
>
> 我：？？？
>
> 说实话，这种行为让我很不爽。Vibe Coding 时代，对于会用智能 IDE 的人来说，做这些东西根本没什么技术壁垒。与其让某些人靠信息差割韭菜，不如直接开源，让每个人都能用。
>
> 所以我花了点时间把它复现出来，然后开源了。就这么简单。
>
> **对那些靠卖这种东西赚钱的朋友：不好意思，砸你们场子了。** 😎

---

## ✨ 功能特点

- 🔄 **无限对话** - AI 完成任务后自动弹窗询问是否继续
- 📋 **剪贴板图片** - 支持 Ctrl+V 粘贴截图
- 🖱️ **拖拽上传** - 拖拽图片到对话框
- 🌍 **全局规则** - 一次配置，所有项目通用

## 🚀 快速安装

**Windows**: 双击运行 `install.bat`

安装完成后重启 Windsurf 即可使用。

## 📖 手动安装

### 1. 安装 Python 依赖

```bash
cd mcp-server-python
pip install -r requirements.txt
```

### 2. 安装 Windsurf 扩展

按 `Ctrl+Shift+P` → 输入 `Extensions: Install from VSIX` → 选择 `windsurf-ask-continue-1.0.9.vsix`

### 3. 配置 MCP

编辑 `~/.codeium/windsurf/mcp_config.json`：

```json
{
  "mcpServers": {
    "ask-continue": {
      "command": "python",
      "args": ["你的路径/Windsurf_Ask_Continue/mcp-server-python/server.py"]
    }
  }
}
```

### 4. 配置全局规则

复制 `rules/example-windsurfrules.txt` 到 `~/.windsurfrules`

## 📁 项目结构

```
├── install.bat              # 一键安装
├── mcp-server-python/       # MCP 服务器
│   ├── server.py
│   └── requirements.txt
├── vscode-extension/        # Windsurf 扩展源码
└── rules/                   # 规则模板
```

## � 常用操作

| 操作 | 方法 |
|------|------|
| **重新打开弹窗** | `Ctrl+Shift+P` → `Ask Continue: Open Panel` |
| 查看状态 | `Ctrl+Shift+P` → `Ask Continue: Show Status` |
| 重启服务 | `Ctrl+Shift+P` → `Ask Continue: Restart Server` |

## �🔧 故障排除

| 问题 | 解决方案 |
|------|----------|
| 弹窗不出现 | 检查状态栏是否显示 "Ask Continue: 23983" |
| 不小心关了弹窗 | 用上面的命令重新打开 |
| MCP 不可用 | 重启 Windsurf |
| 端口冲突 | 设置中修改 `askContinue.serverPort` |

## ⚠️ 使用声明

**本项目完全免费开源，禁止任何形式的二次打包售卖！**

如果你在闲鱼、淘宝或其他平台看到有人售卖此工具，请直接举报。

## 📄 License

**CC BY-NC-SA 4.0** (署名-非商业性使用-相同方式共享)

- ✅ 可以自由使用、修改、分享
- ✅ 需要注明原作者 (Rhongomiant1227)
- ❌ **禁止商业用途**
- ❌ **禁止二次打包售卖**

详见 [LICENSE](./LICENSE) 文件
