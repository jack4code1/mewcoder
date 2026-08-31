# MewCode

MewCode 是一个基于 Python 和 Textual 的终端 AI 编程助手。它把模型对话、项目上下文、工具调用和安全审批整合到一个终端界面中，适合在真实代码库中进行查询、修改、测试和多步骤任务协作。

## 项目亮点

- 多模型接入：支持 OpenAI 兼容接口、Claude、Ollama 以及自定义 Provider。
- 终端交互界面：基于 Textual 构建，支持会话恢复、模型切换、Token 用量和运行时长展示。
- 工具系统：提供文件读取、文件编辑、差异查看、目录匹配、内容搜索和 Bash 工具。
- 安全控制：写文件和执行命令等状态变更操作默认需要用户审批，并记录审批和审计信息。
- 多智能体编排：支持角色、任务依赖、工具权限、取消控制、预算限制和结构化执行结果。
- 项目记忆：保存会话和项目级上下文，支持检索、自动提取以及可选的向量嵌入。
- MCP 扩展：支持通过 MCP stdio 服务扩展外部工具，服务需要在配置中显式启用。

## 技术栈

- Python 3.10+
- Textual、Rich
- HTTPX、PyYAML
- pytest、pytest-asyncio

## 安装

```bash
python -m pip install .
```

开发环境（包含测试依赖）：

```bash
python -m pip install -e ".[dev]"
```

## 配置和运行

1. 根据需要修改 `config.yaml` 中的模型和 Provider。
2. 将对应的 API Key 放入环境变量，例如 `ZAI_API_KEY` 或 `MIMO_API_KEY`。
3. 启动终端应用：

```bash
mewcode
```

也可以在启动时指定模型和 Provider：

```bash
mewcode --model glm-5.2 --provider openai
```

本地配置可以放在被 Git 忽略的 `config.local.yaml` 中，避免把密钥提交到仓库。使用 Ollama 时，需要先在本机启动 Ollama 服务并准备对应模型。

## 安全模型

项目默认开启安全审批。文件写入、文件编辑和 Shell 命令等可能改变工作区状态的操作，需要在终端中明确批准；只读工具可以按配置单独开放。审批记录和项目权限保存在 `.mewcode/` 下，该目录不会提交到 Git。

## 核心结构

```text
src/mewcode/
├── cli.py                         命令行参数和入口
├── tui/                           Textual 终端界面
├── engine/agent.py                Agent 循环和模型调用
├── engine/adapters/               不同模型 Provider 的适配器
├── engine/tools/                  文件、搜索、差异和 Shell 工具
├── engine/security/               审批、权限和审计
├── engine/context/                上下文压缩、预算和项目记忆
└── engine/orchestration/          多智能体任务编排和隔离工作树
```

## 测试

运行完整测试套件：

```bash
python -m pytest -q
```

## 许可证

本项目采用 MIT License。
