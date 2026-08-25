# MewCode 操作手册

## 快速开始

### 安装依赖

```bash
python -m venv .venv
# macOS/Linux
.venv/bin/python -m pip install -e ".[dev]"
# Windows PowerShell
.venv\Scripts\python -m pip install -e ".[dev]"
```

### 启动 MewCode

```bash
mewcode
# 或
python -m mewcode
```

---

## 界面说明

```
┌─────────────────────────────────────────────────────────────┐
│  Header                                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  对话区域                                                    │
│  - 显示用户消息和 AI 回复                                    │
│  - 支持 Markdown 渲染                                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [mimo-v2.5-pro] [Tokens: N/A] [Avg: N/A] [Idle] [Chat]   │  ← 状态栏，仅在输入时显示
│  >>> 输入框                                                  │  ← 至少一行
└─────────────────────────────────────────────────────────────┘
```

> 状态栏位于输入框正上方：输入框有内容时显示，输入框为空（含提交后、流式刷新期间）时隐藏，隐藏时不占布局空间，由对话区回收。输入框在任何终端尺寸下至少完整显示一行。

---

## 基本操作

### 发送消息

1. 在输入框中输入消息
2. 按 `Enter` 发送,输入栏会自动清空
3. 等待 AI 回复（流式显示）。如果模型需要工具,MewCode 会自动进入多轮 Agent Loop,直到任务完成或触发停止条件。
4. 可用 `↑` / `↓` 快速切换历史提示词。

### 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/copy` | 复制最后一条 AI 回复到剪贴板 |
| `/clear` | 清空对话 |
| `/save` | 保存当前会话 |
| `/model` | 切换模型（待实现） |
| `/mode` | 切换对话/单次模式 |
| `/context` | 查看当前上下文预算摘要 |
| `/memory` | 查看项目记忆 |
| `/remember <内容>` | 保存项目记忆 |
| `/forget <id>` | 删除项目记忆 |
| `/audit` | 查看最近安全审计记录（启用安全模式时） |
| `/quit` | 退出程序 |

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息并清空输入栏 |
| `Ctrl+C` | 退出程序 |
| `Ctrl+L` | 清空屏幕 |
| `Ctrl+S` | 保存会话 |
| `Ctrl+T` | 切换模式 |
| `Ctrl+Shift+C` | 复制最后一条 AI 回复 |
| `Esc` | 取消当前 Agent Loop,不退出程序 |
| `F1` 或 `Ctrl+H` | 显示帮助 |
| `↑` / `↓` | 浏览历史提示词 |
| `Tab` | 命令补全 |

### 复制 AI 回复

对话区域的文本支持鼠标选择复制（流式输出完成后）。也可以使用以下方式快速复制：

- 输入 `/copy` 命令
- 按 `Ctrl+Shift+C`

内容会复制到系统剪贴板。

---

## 配置说明

### 配置文件位置

仓库根目录的 `config.yaml`

### 配置示例

推荐把 API Key 放在环境变量中；当环境变量不存在或为空时，MewCode 会继续使用 `api_key` 字段中的明文 fallback。

```yaml
# LLM 配置
llm:
  default_model: "mimo-v2.5-pro"
  default_provider: "custom"

  models:
    mimo-v2.5-pro:
      provider: "custom"
      base_url: "https://token-plan-cn.xiaomimimo.com/v1"
      api_key_env: "MIMO_API_KEY"
      api_key: "your-api-key-fallback"
      api_format: "openai"
      model: "mimo-v2.5-pro"

# 会话配置
session:
  storage_dir: "~/.mewcode/sessions"
  auto_save: true

# TUI 配置
tui:
  theme: "default"
  show_token_usage: true
  show_session_duration: true
```

PowerShell 示例：

```powershell
$env:MIMO_API_KEY="your-api-key"
.\start.ps1
```

### 支持的模型

| 提供商 | 模型 | 说明 |
|--------|------|------|
| OpenAI | gpt-4, gpt-3.5-turbo | 需要 OpenAI API Key |
| Claude | claude-3-5-sonnet | 需要 Anthropic API Key |
| Ollama | llama2, mistral | 需要本地 Ollama 服务 |
| 自定义 | mimo-v2.5-pro | 小米 MiMo API |

### 上下文、记忆与安全

MewCode 会按项目上下文预算裁剪发送给模型的消息，可通过 `/context` 查看摘要。`/memory`、`/remember` 和 `/forget` 管理当前工作目录下的项目记忆。

安全审批默认开启：状态变更工具会请求授权，而只读工具可直接运行。可使用 `/approve`、`/deny` 和 `/audit` 管理授权与查看审计记录。仅可信自动化场景应在被忽略的 `config.local.yaml` 中显式设置 `security.enabled: false`。

MCP、Hooks、任务编排、Worktrees 与 Agent Teams 目前仅提供基础模块，尚未形成可从 TUI 完成的工作流。

任务编排支持在干净 Git Worktree 中运行受限任务、收集可审阅 diff 并管理租约；团队协调器可拒绝重叠上下文并限制并发。

### 隔离子任务与审阅

`/task <目标>` 在干净主工作区上创建隔离 Worktree。子任务的写入、命令和外部工具请求会显示主 TUI 审批卡。使用 `/tasks` 查看结果；用 `/task apply <id>` 应用 diff，或用 `/task discard <id>` 丢弃租约。

### Revision、记忆与 Skills

写入和编辑前会保存 revision。`/diff` 列出可用 revision，`/rollback <id>` 恢复原内容。`/memory search <查询>` 搜索项目记忆，`/summarize` 压缩较早会话历史。使用 `/skill add <名称> <指令>` 与 `/skill delete <名称>` 管理项目 Skills。

### 项目 Hooks

可在 `.mewcode/hooks.yaml` 配置 `task_start` 或 `task_complete` 的 Bash Hook。Hook 和普通 Bash 工具一样受安全审批保护；先使用 `/approve project Bash` 授权，未授权的 Hook 会阻止该次任务执行。

```yaml
hooks:
  - event: task_start
    name: focused-tests
    command: python -m pytest -q
```

### 项目 Skills

将 UTF-8 Markdown 指令保存到项目的 `.mewcode/skills/` 目录，MewCode 会在每次请求前自动加载。文件名（不含 `.md`）是 Skill 名称；使用 `/skills` 查看当前加载结果。

---

## 使用示例

### 基本对话

```
>>> 你好，请介绍一下自己
MewCode: 你好！我是 MewCode，一个终端 AI 编程助手...
```

### 代码生成

```
>>> 写一个 Python 函数计算斐波那契数列
MewCode: 
```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```
```

### 代码解释

```
>>> 解释一下这段代码的作用
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

MewCode: 这是一个快速排序算法的实现...
```

---

## 会话管理

### 保存会话

输入 `/save` 命令或按 `Ctrl+S` 保存当前会话。

会话文件保存在：`~/.mewcode/sessions/`

### 会话持久化

- 会话自动保存在 YAML 文件中
- 包含消息历史、Token 统计等信息
- 可以手动复制会话文件进行备份

---

## 日志查看

### 日志位置

`~/.mewcode/logs/mewcode.log`

### 查看日志

```powershell
cat ~/.mewcode/logs/mewcode.log
```

---

## 故障排除

### 问题：启动失败

**解决方案**：
1. 检查 Python 版本（需要 3.10+）
2. 检查依赖是否安装：`pip install textual httpx pyyaml rich`
3. 检查 API Key 是否正确

### 问题：API 调用失败

**解决方案**：
1. 检查网络连接
2. 检查 API Key 是否有效
3. 检查模型名称是否正确

### 问题：流式输出不显示

**解决方案**：
1. 检查日志文件
2. 尝试重启程序
3. 检查 API 是否支持流式输出

---

## 开发者指南

### 运行测试

```powershell
python -m pytest
```

### 添加新模型

1. 在 `src/mewcode/engine/adapters/` 创建新适配器
2. 继承 `LLMClient` 基类
3. 实现 `chat` 和 `chat_stream` 方法
4. 在 `AdapterFactory` 中注册

### 自定义主题

修改 `src/mewcode/tui/app.py` 中的 CSS 样式。

---

## 联系方式

- 项目地址：当前 Git 仓库根目录
- 日志位置：~/.mewcode/logs/
- 会话位置：~/.mewcode/sessions/
## UI Layout Note

The chat area is always the main visible region. The status bar appears above
the input only while there is draft text, and the input box stays compact as a
single-line control. If the terminal is resized, the input must not expand to
hide assistant output or tool traces.

## Token Metrics Status Bar

The status bar shows real API metrics when the provider returns enough data:

- `Tokens`: total token usage, with prompt/completion split on wide terminals.
- `tok/s`: average output token speed.
- `TTFT`: average first-token latency.
- `Lat`: average total API latency.
- `N/A`: displayed when usage or timing data is unavailable.

Session YAML saves aggregate `api_metrics` and message-level `token_usage` when available.
