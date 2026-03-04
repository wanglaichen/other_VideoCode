# AgentTest 使用文档

## 1. 项目说明

这是一个基于 ReAct 模式的本地 Agent 示例：

- 通过大模型输出 `<thought>` + `<action>/<final_answer>` 驱动流程
- 可调用 3 个本地工具：`read_file`、`write_to_file`、`run_terminal_command`
- 目标目录由命令参数传入（例如 `snake`）

---

## 2. 本次排查结论（已落地）

本项目已经完成以下修复和约束：

1. 模型服务切换为硅基流动（兼容 OpenAI SDK）。
2. 默认模型设置为 `Qwen/Qwen2.5-7B-Instruct`。
3. 启动参数目录如果不存在会自动创建，不再因目录缺失退出。
4. 对模型 `<action>` 解析增加容错，降低格式波动导致的中断。
5. 对“写代码”类请求增加约束：优先落盘（调用 `write_to_file`）再结束。
6. `write_to_file` 增强路径修复和目录自动创建，避免 Windows 反斜杠转义导致失败。
7. Windows 中文输入乱码（`???`）增加检测与明确提示。

---

## 3. 基础配置

### 3.1 前置依赖

先安装 `uv`（若未安装）：

https://docs.astral.sh/uv/guides/install-python/

### 3.2 环境变量 `.env`

在项目根目录创建 `.env`（UTF-8 编码），最小配置如下：

```env
SILICONFLOW_API_KEY=你的硅基流动API密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=Qwen/Qwen2.5-7B-Instruct
```

变量说明：

- `SILICONFLOW_API_KEY`：必填，硅基流动 key。
- `SILICONFLOW_BASE_URL`：可选，默认 `https://api.siliconflow.cn/v1`。
- `SILICONFLOW_MODEL`：可选，默认 `Qwen/Qwen2.5-7B-Instruct`。

---

## 4. 详细使用方式

### 4.1 启动命令

```bash
uv run agent.py snake
```

说明：

1. `snake` 是“项目工作目录”参数。
2. 如果该目录不存在，程序会自动创建。
3. 进入交互后会提示 `请输入任务：`。

### 4.2 Windows 中文输入建议

在 Windows 下建议先执行：

```powershell
chcp 65001
```

然后再运行 Agent，避免中文输入在终端被编码成 `???`。

### 4.3 交互规则

1. 输入任务后，Agent 会循环输出 `Thought / Action / Observation`。
2. 当模型调用 `run_terminal_command` 时，会询问 `是否继续？（Y/N）`。
3. 其他工具调用默认直接执行。
4. 任务结束时输出 `[Final Answer] ...`。

---

## 5. 代码生成任务的行为

当你输入“写代码/写程序/实现功能”等任务时：

1. Agent 会尽量先调用 `write_to_file` 落盘，再给最终答复。
2. 写入路径会被约束到你传入的项目目录内（例如 `snake`）。
3. 如果模型给了错误路径格式（常见于 Windows 反斜杠转义），程序会做修正。

建议用法：

1. 启动：`uv run agent.py snake`
2. 输入：`帮我用python写一个贪吃蛇游戏`
3. 观察输出里的写入路径（应在 `snake` 目录下）
4. 任务结束后去对应文件查看代码

---

## 6. 常见问题与处理

### Q1: `Invalid value for 'PROJECT_DIRECTORY': Directory 'xxx' does not exist.`

A：已修复，当前版本会自动创建目录。若仍出现，请确认运行的是最新代码。

### Q2: `401` / 鉴权失败

A：通常是 key 无效或配置错误。检查：

1. `.env` 是否包含正确的 `SILICONFLOW_API_KEY`
2. `SILICONFLOW_BASE_URL` 是否为 `https://api.siliconflow.cn/v1`

### Q3: 模型回复“问题不完整”或把中文识别成 `???`

A：终端编码问题，先执行 `chcp 65001` 再启动。

### Q4: 最终回答给了代码，但没有生成文件

A：现在已加“写代码优先落盘”约束。若偶发未写入，重试一次同任务，或在任务中明确追加“请把完整代码写入文件”。

### Q5: `run_terminal_command` 后出现编码异常

A：已改为 UTF-8 解码并容错。若命令输出异常字符，优先检查系统终端编码设置。

---

## 7. 安全建议

1. 不要把真实 API Key 提交到 Git 仓库。
2. 如果 key 在聊天或日志中泄露，建议立即在平台后台轮换/重置。
