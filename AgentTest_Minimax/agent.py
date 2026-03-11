import ast
import inspect
import os
import re
import sys
from string import Template
from typing import List, Callable, Tuple

import click
from dotenv import load_dotenv
from openai import OpenAI
import platform

from prompt_template import react_system_prompt_template


def configure_console_utf8() -> None:
    """Best-effort UTF-8 setup for Windows console I/O."""
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        # Non-fatal: some environments do not expose Win32 console APIs.
        pass

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


class ReActAgent:
    def __init__(self, tools: List[Callable], model: str, project_directory: str):
        self.tools = { func.__name__: func for func in tools }
        self.model = model
        self.project_directory = project_directory
        self.client = OpenAI(
            base_url=ReActAgent.get_base_url(),
            api_key=ReActAgent.get_api_key(),
        )

    @staticmethod
    def _to_utf8_safe_text(value) -> str:
        text = value if isinstance(value, str) else str(value)
        return text.encode("utf-8", errors="replace").decode("utf-8")

    @classmethod
    def _to_utf8_safe_messages(cls, messages):
        safe_messages = []
        for message in messages:
            safe_messages.append(
                {
                    "role": message.get("role", "user"),
                    "content": cls._to_utf8_safe_text(message.get("content", "")),
                }
            )
        return safe_messages

    def run(self, user_input: str):
        safe_user_input = self._to_utf8_safe_text(user_input)
        messages = [
            {
                "role": "system",
                "content": self._to_utf8_safe_text(
                    self.render_system_prompt(react_system_prompt_template)
                ),
            },
            {"role": "user", "content": f"<question>{safe_user_input}</question>"}
        ]
        format_retry_count = 0
        write_retry_count = 0
        has_write_action = False
        is_code_task = self._is_code_generation_request(user_input)
        default_code_path = os.path.abspath(os.path.join(self.project_directory, "snake_game.py"))

        while True:

            # 请求模型
            content = self.call_model(messages)

            # 检测 Thought
            thought_match = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1)
                print(f"\n\n[Thought] {thought}")

            # 检测模型是否输出 Final Answer，如果是的话，直接返回
            if "<final_answer>" in content:
                final_answer = re.search(r"<final_answer>(.*?)</final_answer>", content, re.DOTALL)
                final_text = final_answer.group(1).strip()
                if is_code_task and not has_write_action and write_retry_count < 2:
                    write_retry_count += 1
                    messages.append({
                        "role": "user",
                        "content": (
                            "你还没有调用 write_to_file 保存代码文件。"
                            f"请先执行：<action>write_to_file(\"{default_code_path}\", \"完整代码\")</action>。"
                            "写入成功后，再输出 <final_answer>，并在答案中写明绝对路径。"
                        )
                    })
                    continue
                return final_text

            # 检测 Action
            action_match = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            if not action_match:
                # Fallback for providers/models that do not strictly follow the tag protocol.
                cleaned = re.sub(r"<thought>.*?</thought>", "", content, flags=re.DOTALL).strip()
                if cleaned:
                    return cleaned
                if format_retry_count >= 2:
                    raise RuntimeError("模型未输出 <action> 或 <final_answer>")
                format_retry_count += 1
                messages.append({
                    "role": "user",
                    "content": "请严格输出：<final_answer>你的最终答案</final_answer>。不要输出其他标签。"
                })
                continue
            action = action_match.group(1)
            try:
                tool_name, args = self.parse_action(action)
            except Exception:
                if format_retry_count >= 2:
                    raise RuntimeError("模型输出了 <action>，但函数调用语法无效")
                format_retry_count += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "你的 <action> 语法不合法。请严格只输出一个函数调用，"
                        "例如：<action>read_file(\"E:/a.txt\")</action> 或 "
                        "<action>write_to_file(\"E:/a.txt\", \"hello\")</action>。"
                    )
                })
                continue

            if tool_name not in self.tools:
                if format_retry_count >= 2:
                    raise RuntimeError(f"模型调用了不存在的工具：{tool_name}")
                format_retry_count += 1
                available_tools = ", ".join(self.tools.keys())
                messages.append({
                    "role": "user",
                    "content": (
                        f"你调用了不存在的工具 `{tool_name}`。"
                        f"请只使用这些工具：{available_tools}。"
                        "重新输出一个合法的 <action> 或直接输出 <final_answer>。"
                    )
                })
                continue

            if tool_name == "write_to_file" and len(args) >= 1:
                args[0] = self._coerce_project_path(str(args[0]))

            print(f"\n\n[Action] {tool_name}({', '.join(map(str, args))})")
            # 只有终端命令才需要询问用户，其他的工具直接执行
            should_continue = input(f"\n\n是否继续？（Y/N）") if tool_name == "run_terminal_command" else "y"
            if should_continue.lower() != 'y':
                print("\n\n操作已取消。")
                return "操作被用户取消"

            try:
                observation = self.tools[tool_name](*args)
            except Exception as e:
                observation = f"工具执行错误：{str(e)}"
            if tool_name == "write_to_file" and "写入成功" in str(observation):
                has_write_action = True
            print(f"\n\n[Observation] {observation}")
            obs_msg = f"<observation>{observation}</observation>"
            messages.append({"role": "user", "content": obs_msg})


    def get_tool_list(self) -> str:
        """生成工具列表字符串，包含函数签名和简要说明"""
        tool_descriptions = []
        for func in self.tools.values():
            name = func.__name__
            signature = str(inspect.signature(func))
            doc = inspect.getdoc(func)
            tool_descriptions.append(f"- {name}{signature}: {doc}")
        return "\n".join(tool_descriptions)

    def render_system_prompt(self, system_prompt_template: str) -> str:
        """渲染系统提示模板，替换变量"""
        tool_list = self.get_tool_list()
        file_list = ", ".join(
            os.path.abspath(os.path.join(self.project_directory, f))
            for f in os.listdir(self.project_directory)
        )
        return Template(system_prompt_template).substitute(
            operating_system=self.get_operating_system_name(),
            tool_list=tool_list,
            file_list=file_list
        )

    @staticmethod
    def get_api_key() -> str:
        """Load the API key from an environment variable."""
        # Use utf-8-sig to tolerate BOM when .env is written by Windows tools.
        load_dotenv(dotenv_path=".env", encoding="utf-8-sig")
        api_key = (
            os.getenv("MINIMAX_API_KEY")
            or os.getenv("SILICONFLOW_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
        )
        if not api_key:
            raise ValueError(
                "API key not found. Set MINIMAX_API_KEY in .env "
                "(you can copy .env.example to .env first)."
            )
        return api_key

    @staticmethod
    def get_base_url() -> str:
        """Load base URL from env, defaulting to MiniMax OpenAI-compatible endpoint."""
        load_dotenv(dotenv_path=".env", encoding="utf-8-sig")
        return (
            os.getenv("MINIMAX_BASE_URL")
            or os.getenv("SILICONFLOW_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or "https://api.minimaxi.com"
        )

    def call_model(self, messages):
        print("\n\n正在请求模型，请稍等...")
        safe_messages = self._to_utf8_safe_messages(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=safe_messages,
        )
        content = self._to_utf8_safe_text(response.choices[0].message.content or "")
        messages.append({"role": "assistant", "content": content})
        return content

    def parse_action(self, code_str: str) -> Tuple[str, List[str]]:
        code_str = self._extract_call_expression(code_str)
        match = re.match(r'([A-Za-z_]\w*)\s*\((.*)\)\s*$', code_str, re.DOTALL)
        if not match:
            raise ValueError("Invalid function call syntax")

        func_name = match.group(1)
        args_str = match.group(2).strip()

        # 手动解析参数，特别处理包含多行内容的字符串
        args = []
        current_arg = ""
        in_string = False
        string_char = None
        i = 0
        paren_depth = 0
        
        while i < len(args_str):
            char = args_str[i]
            
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    string_char = char
                    current_arg += char
                elif char == '(':
                    paren_depth += 1
                    current_arg += char
                elif char == ')':
                    paren_depth -= 1
                    current_arg += char
                elif char == ',' and paren_depth == 0:
                    # 遇到顶层逗号，结束当前参数
                    args.append(self._parse_single_arg(current_arg.strip()))
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char
                if char == string_char and (i == 0 or args_str[i-1] != '\\'):
                    in_string = False
                    string_char = None
            
            i += 1
        
        # 添加最后一个参数
        if current_arg.strip():
            args.append(self._parse_single_arg(current_arg.strip()))
        
        return func_name, args

    def _extract_call_expression(self, raw: str) -> str:
        """Extract a single function-call expression from model action text."""
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty action")

        # If the model wraps the call in a code fence, keep only fenced content.
        fence_match = re.search(r"```(?:\w+)?\s*(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Normalize common full-width punctuation in Chinese outputs.
        text = text.replace("（", "(").replace("）", ")")

        # Trim possible prefixes like "Action:" / "动作：".
        text = re.sub(r"^\s*(Action|动作)\s*[:：]\s*", "", text, flags=re.IGNORECASE)

        # Find first function call start.
        start_match = re.search(r"[A-Za-z_]\w*\s*\(", text)
        if not start_match:
            raise ValueError("No function call found in action")
        start = start_match.start()

        # Parse until matching closing parenthesis, while respecting quoted strings.
        in_string = False
        string_char = ""
        escaped = False
        depth = 0
        end = None
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == string_char:
                    in_string = False
                continue
            if ch in ("'", '"'):
                in_string = True
                string_char = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end is None:
            raise ValueError("Unbalanced parentheses in action")
        return text[start:end + 1].strip()
    
    def _parse_single_arg(self, arg_str: str):
        """解析单个参数"""
        arg_str = arg_str.strip()
        
        # 如果是字符串字面量
        if (arg_str.startswith('"') and arg_str.endswith('"')) or \
           (arg_str.startswith("'") and arg_str.endswith("'")):
            # 移除外层引号并处理转义字符
            inner_str = arg_str[1:-1]
            # 处理常见的转义字符
            inner_str = inner_str.replace('\\"', '"').replace("\\'", "'")
            inner_str = inner_str.replace('\\n', '\n').replace('\\t', '\t')
            inner_str = inner_str.replace('\\r', '\r').replace('\\\\', '\\')
            return inner_str
        
        # 尝试使用 ast.literal_eval 解析其他类型
        try:
            return ast.literal_eval(arg_str)
        except (SyntaxError, ValueError):
            # 如果解析失败，返回原始字符串
            return arg_str

    def _coerce_project_path(self, candidate_path: str) -> str:
        """Force write path to stay inside current project directory."""
        text = (candidate_path or "").strip()
        text = (
            text.replace("\t", "\\t")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\\\\", "\\")
        )
        if not os.path.isabs(text):
            text = os.path.join(self.project_directory, text)
        abs_path = os.path.abspath(os.path.normpath(text))
        project_root = os.path.abspath(self.project_directory)
        try:
            in_project = os.path.commonpath([abs_path, project_root]) == project_root
        except ValueError:
            in_project = False
        if in_project:
            return abs_path
        return os.path.abspath(os.path.join(project_root, "snake_game.py"))

    @staticmethod
    def _is_code_generation_request(user_input: str) -> bool:
        """Heuristic: determine whether user asks to generate source code."""
        if not user_input:
            return False
        text = user_input.strip().lower()
        cn_code_terms = ("代码", "程序", "脚本", "游戏", "项目")
        cn_action_terms = ("写", "生成", "实现", "开发", "做")
        en_action_terms = ("write", "create", "build", "implement", "generate")
        en_code_terms = ("code", "program", "script", "game", "app")

        has_cn_signal = any(a in user_input for a in cn_action_terms) and any(c in user_input for c in cn_code_terms)
        has_en_signal = any(a in text for a in en_action_terms) and any(c in text for c in en_code_terms)
        has_python_signal = "python" in text and any(a in user_input for a in ("写", "实现", "生成", "开发"))
        return has_cn_signal or has_en_signal or has_python_signal

    def get_operating_system_name(self):
        os_map = {
            "Darwin": "macOS",
            "Windows": "Windows",
            "Linux": "Linux"
        }

        return os_map.get(platform.system(), "Unknown")


def read_file(file_path):
    """用于读取文件内容"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def write_to_file(file_path, content):
    """将指定内容写入指定文件"""
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path 必须是非空字符串")

    # Recover common escape-damage from model output such as \t \n \r in Windows paths.
    normalized_path = (
        file_path.strip()
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\\\\", "\\")
    )
    normalized_path = os.path.normpath(normalized_path)
    parent_dir = os.path.dirname(normalized_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(normalized_path, "w", encoding="utf-8") as f:
        f.write(content.replace("\\n", "\n"))
    return f"写入成功: {normalized_path}"

def run_terminal_command(command):
    """用于执行终端命令"""
    import subprocess
    run_result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if run_result.returncode == 0:
        return run_result.stdout.strip() or "执行成功"
    return run_result.stderr.strip() or "执行失败"


def looks_like_garbled_input(text: str) -> bool:
    """Heuristic for mojibake-like input on Windows terminals (e.g. many '?')."""
    if not text:
        return False
    q_count = text.count("?")
    return q_count >= 3 and (q_count / max(len(text), 1)) >= 0.2

@click.command()
@click.argument('project_directory',
                type=click.Path(exists=False, file_okay=False, dir_okay=True))
def main(project_directory):
    configure_console_utf8()

    project_dir = os.path.abspath(project_directory)
    if os.path.exists(project_dir) and not os.path.isdir(project_dir):
        raise click.ClickException(f"Path exists but is not a directory: {project_dir}")
    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
        print(f"[Info] Directory created: {project_dir}")
    load_dotenv(dotenv_path=".env", encoding="utf-8-sig")

    tools = [read_file, write_to_file, run_terminal_command]
    model = (
        os.getenv("MINIMAX_MODEL")
        or os.getenv("SILICONFLOW_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or "MiniMax-M2.5"
    )
    agent = ReActAgent(tools=tools, model=model, project_directory=project_dir)

    task = ReActAgent._to_utf8_safe_text(input("Enter task: "))
    if looks_like_garbled_input(task):
        raise click.ClickException(
            "Input may be garbled (contains too many '?'). Run `chcp 65001` and try again."
        )

    try:
        final_answer = agent.run(task)
    except Exception as e:
        raise click.ClickException(f"Model request failed: {e}")

    print(f"\n\n[Final Answer] {final_answer}")

if __name__ == "__main__":
    main()
