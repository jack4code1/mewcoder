# MewCode 操作手册

## 快速开始

### 安装依赖

```bash
pip install textual httpx pyyaml rich
```

### 启动 MewCode

#### 方式 1: PowerShell
```powershell
cd E:\agent_class\project
.\start.ps1
```

#### 方式 2: CMD
```cmd
cd E:\agent_class\project
start.bat
```

#### 方式 3: 直接命令
```powershell
cd E:\agent_class\project
$env:PYTHONPATH="E:\agent_class\project\src"
python -c "from mewcode.tui.app import run_app; run_app(model='mimo-v2.5-pro', provider='custom')"
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
│  >>> 输入框                                                  │
├─────────────────────────────────────────────────────────────┤
│  [mimo-v2.5-pro] [Tokens: N/A] [Avg: N/A] [Idle] [Chat]   │
└─────────────────────────────────────────────────────────────┘
```

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

`E:\agent_class\project\config.yaml`

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
$env:PYTHONPATH="E:\agent_class\project\src"
python -m pytest tests/ -v
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

- 项目地址：E:\agent_class\project
- 日志位置：~/.mewcode/logs/
- 会话位置：~/.mewcode/sessions/
## Token Metrics Status Bar

The status bar shows real API metrics when the provider returns enough data:

- `Tokens`: total token usage, with prompt/completion split on wide terminals.
- `tok/s`: average output token speed.
- `TTFT`: average first-token latency.
- `Lat`: average total API latency.
- `N/A`: displayed when usage or timing data is unavailable.

Session YAML saves aggregate `api_metrics` and message-level `token_usage` when available.
