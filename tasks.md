# MewCode - 任务清单

## 阶段目标

完成一个可以调用适配多种 LLM 和不同 API 协议的可以进行流式对话的 agent 工具，并且有初步的 TUI 界面，并且模块化编程后期可以便捷的增加/修改功能。

---

## 任务 1：项目基础搭建
**影响文件**：`pyproject.toml`, `src/mewcode/__init__.py`, `src/mewcode/main.py`, `src/mewcode/cli.py`
**依赖任务**：无
**说明**：
- 初始化 Python 项目结构
- 配置 pyproject.toml（依赖：textual, httpx, pyyaml）
- 创建基础入口文件

## 任务 2：数据模型定义
**影响文件**：`src/mewcode/engine/models/message.py`, `src/mewcode/engine/models/client.py`
**依赖任务**：任务 1
**说明**：
- 定义 Message、MessageRole 数据类
- 定义 TokenUsage 数据类
- 定义 LLMResponse、StreamChunk 数据类
- 定义 LLMClient 抽象基类（chat、chat_stream、validate_connection 接口）

## 任务 3：OpenAI 适配器
**影响文件**：`src/mewcode/engine/adapters/openai_adapter.py`
**依赖任务**：任务 2
**说明**：
- 实现 OpenAI API 格式的非流式请求
- 实现 OpenAI API 格式的 SSE 流式请求
- 实现连接验证
- 消息格式转换

## 任务 4：Claude 适配器
**影响文件**：`src/mewcode/engine/adapters/claude_adapter.py`
**依赖任务**：任务 2
**说明**：
- 实现 Claude API 格式的非流式请求
- 实现 Claude API 格式的 SSE 流式请求
- 实现连接验证
- 消息格式转换（分离 system 消息）

## 任务 5：Ollama 适配器
**影响文件**：`src/mewcode/engine/adapters/ollama_adapter.py`
**依赖任务**：任务 2
**说明**：
- 实现 Ollama API 格式的非流式请求
- 实现 Ollama API 格式的流式请求
- 实现连接验证

## 任务 6：自定义端点适配器
**影响文件**：`src/mewcode/engine/adapters/custom_adapter.py`
**依赖任务**：任务 2
**说明**：
- 实现 OpenAI 兼容格式的自定义端点
- 实现通用格式的自定义端点
- 支持配置 API 格式

## 任务 7：适配器工厂
**影响文件**：`src/mewcode/engine/adapters/factory.py`, `src/mewcode/engine/adapters/__init__.py`
**依赖任务**：任务 3, 任务 4, 任务 5, 任务 6
**说明**：
- 实现根据模型名称自动检测提供商
- 实现创建客户端的工厂方法
- 支持列出所有提供商和模型

## 任务 8：对话管理器
**影响文件**：`src/mewcode/engine/conversation.py`
**依赖任务**：任务 2
**说明**：
- 实现消息历史管理
- 实现 Token 用量统计
- 实现上下文窗口截断
- 实现会话持久化（YAML 格式）
- 实现对话分支和回溯
- 实现多会话管理

## 任务 9：TUI 基础框架
**影响文件**：`src/mewcode/tui/app.py`, `src/mewcode/tui/__init__.py`
**依赖任务**：任务 1
**说明**：
- 创建 Textual 应用主类
- 定义基础布局（对话区域、输入框、状态栏）
- 实现基本的键盘事件处理

## 任务 10：TUI 对话区域组件
**影响文件**：`src/mewcode/tui/widgets/chat_area.py`
**依赖任务**：任务 9
**说明**：
- 实现消息列表显示
- 实现逐字符流式显示效果
- 实现用户消息和 AI 消息的样式区分
- 支持滚动和自动滚动

## 任务 11：TUI 输入框组件
**影响文件**：`src/mewcode/tui/widgets/input_box.py`
**依赖任务**：任务 9
**说明**：
- 实现文本输入
- 实现历史命令（上下键）
- 实现命令补全（/ 开头 + Tab）
- 实现连按两次 Tab 优化提示词
- 支持多行粘贴

## 任务 12：TUI 状态栏组件
**影响文件**：`src/mewcode/tui/widgets/status_bar.py`
**依赖任务**：任务 9
**说明**：
- 实现状态栏显示
- 显示当前模型、Token 用量、会话时长、工作目录、Agent 状态、对话模式
- 支持可配置显示内容

## 任务 13：接入主流程
**影响文件**：`src/mewcode/main.py`, `src/mewcode/cli.py`
**依赖任务**：任务 7, 任务 8, 任务 10, 任务 11, 任务 12
**说明**：
- 将引擎层和 TUI 层集成
- 实现完整的命令行接口
- 处理全局异常和错误
- 实现优雅退出

## 任务 14：端到端验证
**影响文件**：`tests/test_e2e.py`, `tests/fixtures/`
**依赖任务**：任务 13
**说明**：
- 测试 LLM 客户端连接
- 测试流式对话功能
- 测试会话持久化
- 测试 TUI 界面交互

## 任务 15：修复 TUI 流式显示
**影响文件**：`src/mewcode/tui/widgets/chat_area.py`
**依赖任务**：任务 10
**说明**：
- RichLog.write() 不支持 end 参数
- 需要使用缓冲区方式实现流式显示
- 流式内容累积后一次性写入

## 任务 16：修复 TUI 交互问题
**影响文件**：`src/mewcode/tui/widgets/chat_area.py`, `src/mewcode/tui/widgets/input_box.py`
**依赖任务**：任务 15
**说明**：
- 修复流式输出换行问题：同一次回复的流式输出应该在同一行内
- 修复无法复制内容问题：对话区域应支持文本选择
- 修复输入时背景闪烁问题

## 任务 17：添加 Markdown 渲染支持
**影响文件**：`src/mewcode/tui/widgets/chat_area.py`
**依赖任务**：任务 16
**说明**：
- 添加 Markdown 解析器
- 支持代码高亮显示
- 支持标题、列表、粗体、斜体等格式
- 流式输出时实时渲染 Markdown

## 任务 18：修复流式输出实时刷新
**影响文件**：`src/mewcode/tui/widgets/chat_area.py`, `src/mewcode/tui/app.py`
**依赖任务**：任务 17
**说明**：
- 修复流式内容没有实时刷新的问题
- 禁用或重定向日志输出避免闪烁
- 对话区域持续写入流式内容
