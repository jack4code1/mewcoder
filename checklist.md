# MewCode - 验收清单

## 任务 1：项目基础搭建

- [ ] 运行 `python -c "import mewcode"` 不报错
- [ ] `pyproject.toml` 包含 textual, httpx, pyyaml 依赖
- [ ] 项目目录结构符合 spec.md 设计

## 任务 2：数据模型定义

- [ ] 运行 `python -c "from mewcode.engine.models import Message, MessageRole, LLMClient"` 不报错
- [ ] Message 数据类包含 role, content, timestamp, metadata 字段
- [ ] TokenUsage 数据类包含 prompt_tokens, completion_tokens, total_tokens 字段
- [ ] LLMClient 抽象基类定义 chat, chat_stream, validate_connection 方法

## 任务 3：OpenAI 适配器

- [ ] 运行 `python -c "from mewcode.engine.adapters import OpenAIAdapter"` 不报错
- [ ] 配置 OpenAI API key 后，调用 chat 方法返回非空响应
- [ ] 配置 OpenAI API key 后，调用 chat_stream 方法逐字符输出
- [ ] 调用 validate_connection 返回 True

## 任务 4：Claude 适配器

- [ ] 运行 `python -c "from mewcode.engine.adapters import ClaudeAdapter"` 不报错
- [ ] 配置 Claude API key 后，调用 chat 方法返回非空响应
- [ ] 配置 Claude API key 后，调用 chat_stream 方法逐字符输出
- [ ] 调用 validate_connection 返回 True

## 任务 5：Ollama 适配器

- [ ] 运行 `python -c "from mewcode.engine.adapters import OllamaAdapter"` 不报错
- [ ] 启动 Ollama 服务后，调用 chat 方法返回非空响应
- [ ] 启动 Ollama 服务后，调用 chat_stream 方法逐字符输出
- [ ] 调用 validate_connection 返回 True

## 任务 6：自定义端点适配器

- [ ] 运行 `python -c "from mewcode.engine.adapters import CustomAdapter"` 不报错
- [ ] 配置自定义端点后，调用 chat 方法返回非空响应
- [ ] 支持 OpenAI 兼容格式和通用格式

## 任务 7：适配器工厂

- [ ] 运行 `python -c "from mewcode.engine.adapters import AdapterFactory"` 不报错
- [ ] 调用 `AdapterFactory.detect_provider("gpt-4")` 返回 "openai"
- [ ] 调用 `AdapterFactory.detect_provider("claude-3-5-sonnet")` 返回 "claude"
- [ ] 调用 `AdapterFactory.detect_provider("llama2")` 返回 "ollama"
- [ ] 调用 `AdapterFactory.list_providers()` 返回包含 openai, claude, ollama, custom 的列表
- [ ] 调用 `AdapterFactory.create_client("gpt-4", api_key="test")` 返回 OpenAIAdapter 实例

## 任务 8：对话管理器

- [ ] 运行 `python -c "from mewcode.engine.conversation import ConversationManager"` 不报错
- [ ] 创建会话后，添加消息能正确记录历史
- [ ] Token 用量统计正确累加
- [ ] 会话能持久化到 YAML 文件
- [ ] 能从 YAML 文件恢复会话
- [ ] 支持创建多个会话

## 任务 9：TUI 基础框架

- [ ] 运行 `python -m mewcode` 能启动 TUI 界面
- [ ] 界面包含对话区域、输入框、状态栏三个部分
- [ ] 按 Ctrl+C 能正常退出

## 任务 10：TUI 对话区域组件

- [x] 输入消息后，对话区域显示用户消息
- [x] AI 回复时，对话区域逐字符流式显示
- [x] 用户消息和 AI 消息样式不同（颜色区分）
- [ ] 消息过多时支持滚动

## 任务 16：修复 TUI 交互问题

- [ ] 流式输出在同一行内显示，不换行
- [ ] 对话区域支持文本选择和复制
- [ ] 输入时无背景闪烁
- [ ] 输入框输入内容时，背景不闪烁
- [ ] 流式输出完成后自动换行

## 任务 17：添加 Markdown 渲染支持

- [x] LLM 输出的 Markdown 内容正确渲染
- [x] 代码块有语法高亮
- [x] 标题、列表、粗体、斜体正确显示
- [x] 流式输出时实时渲染 Markdown

## 任务 18：修复流式输出实时刷新

- [x] 输入指令后，对话区域实时显示流式内容
- [x] 不会出现日志信息导致的画面闪烁
- [x] 流式内容在同一行内持续更新
- [x] 流式输出完成后自动换行

## 任务 11：TUI 输入框组件

- [ ] 在输入框输入文字后按回车，能发送消息
- [ ] 按上下键能翻阅历史命令
- [ ] 输入 `/` 后按 Tab，能补全命令
- [ ] 连按两次 Tab，能优化当前输入的提示词
- [ ] 支持粘贴多行内容

## 任务 12：TUI 状态栏组件

- [ ] 状态栏显示当前模型名称
- [ ] 状态栏显示 Token 用量（已用/总量）
- [ ] 状态栏显示会话时长
- [ ] 状态栏显示当前工作目录
- [ ] 状态栏显示 Agent 状态（思考中/执行中/空闲）
- [ ] 状态栏显示当前对话模式

## 任务 13：接入主流程

- [ ] 运行 `mewcode` 命令能启动完整应用
- [ ] 能选择不同的 LLM 模型
- [ ] 能进行多轮对话
- [ ] 对话内容能持久化保存
- [ ] 按 Ctrl+S 能保存会话
- [ ] 按 Ctrl+O 能切换模型
- [ ] 按 Ctrl+T 能切换对话模式

## 任务 14：端到端验证

- [ ] 启动 MewCode，选择 OpenAI 模型，输入 "hello"，收到流式回复
- [ ] 启动 MewCode，选择 Claude 模型，输入 "hello"，收到流式回复
- [ ] 启动 MewCode，选择 Ollama 模型，输入 "hello"，收到流式回复
- [ ] 关闭 MewCode 后重新启动，能恢复之前的会话
- [ ] 连续对话 10 轮，Token 用量统计正确
- [ ] 输入 `/help` 显示帮助信息
