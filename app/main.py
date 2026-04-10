from __future__ import annotations

# argparse：解析命令行参数（比如 python main.py --user yjh --model qwen3:8b）
import argparse
# sys：操控 Python 运行环境，这里用于修改模块搜索路径和读取标准输入
import sys
# traceback：程序崩溃时打印完整的错误调用链，方便调试
import traceback
# Path：用面向对象的方式处理文件路径，比字符串拼接更安全
from pathlib import Path

# 当直接用 `python main.py` 运行时，Python 不知道 app/ 目录在哪。
# 这段代码把项目根目录（main.py 往上两级）加入模块搜索路径，
# 这样 `from app.chat.engine import ...` 才能找到对应文件。
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

# generate_reply：发送消息给 Ollama 并返回 AI 的回答
from app.chat.engine import generate_reply
# 从数据库模块导入所有需要用到的函数（都操作 SQLite 数据库）
from app.db.sqlite_store import (
    add_message,             # 把一条消息（用户或AI）存到数据库
    create_session,          # 新建一个对话会话，返回会话ID
    get_connection,          # 获取数据库连接（用 with 语句自动关闭）
    get_latest_session_id,   # 查找该用户最近一次的会话ID
    get_session_title,       # 读取某个会话的标题
    get_or_create_user,      # 查找用户，不存在则自动创建，返回用户ID
    get_recent_messages,     # 从数据库读取最近 N 条对话记录
    init_schema,             # 程序启动时建表（如果表不存在才建，已存在不影响）
    list_user_sessions,      # 列出某用户的所有历史会话
    session_belongs_to_user, # 验证某个会话是否属于当前用户（防止越权）
    update_session_title,    # 修改会话标题
)


# AI 的人设提示词，每次对话都会作为第一条 system 消息发给模型，
# 让模型扮演 SoulMate 这个角色。
SYSTEM_PROMPT = (
    "You are SoulMate, a warm and practical AI companion. "
    "Keep responses concise and helpful."
)

# /history 命令不带数字时默认显示最近 10 条
HISTORY_DEFAULT = 10
# /sessions 命令不带数字时默认显示最近 20 个会话
SESSIONS_DEFAULT = 20


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。
    用户运行程序时可以在命令后面加参数，例如：
      python main.py --user yjh --model qwen3:8b --new-session
    这个函数负责把这些参数读出来，返回一个对象让其他地方用。
    """
    # 创建参数解析器，description 是 --help 时显示的说明文字
    parser = argparse.ArgumentParser(description="SoulMate minimal chat loop")
    # --model：指定用哪个 Ollama 模型，不填就用 qwen3:8b-q4_K_M
    parser.add_argument("--model", default="qwen3:8b-q4_K_M", help="Ollama model name")
    # --user：指定用户名，用于在数据库里区分不同用户的数据
    parser.add_argument("--user", default="yjh", help="User name for local profile")
    # --ask：如果填了这个参数，程序只回答这一个问题就退出，不进入对话循环
    parser.add_argument(
        "--ask",
        default="",
        help="Run one-shot chat with a single question, then exit",
    )
    # --new-session：加上这个参数会强制开一个新会话，不续接上次的对话
    parser.add_argument(
        "--new-session",
        action="store_true",    # store_true 表示只要写了这个参数就是 True，不写就是 False
        help="Force create a new session instead of reusing latest",
    )
    # --session-id：指定要续接哪个历史会话的 ID
    parser.add_argument(
        "--session-id",
        type=int,       # 强制把输入转成整数，输入字母会报错
        default=0,      # 默认是 0，表示"没有指定"
        help="Reuse a specific existing session id (must belong to --user)",
    )
    # 解析实际的命令行输入，返回含所有参数值的对象
    return parser.parse_args()


def parse_history_limit(command: str) -> int:
    """
    从 /history 命令里解析出要显示多少条记录。
    例如："/history 5" → 返回 5，"/history" → 返回默认值 10。
    如果格式不对（比如 "/history abc"），抛出错误告知用法。
    """
    # 按空格分割命令，"/history 5" 会变成 ["/history", "5"]
    parts = command.split()
    # 只有 "/history" 没带数字，用默认值
    if len(parts) == 1:
        return HISTORY_DEFAULT
    # 带了数字，且数字是合法正整数
    if len(parts) == 2 and parts[1].isdigit():
        value = int(parts[1])
        if value > 0:
            # 最多显示 200 条，防止一次性刷屏太多
            return min(value, 200)
    # 其他情况（比如 "/history -5" 或 "/history abc 1"）格式有误
    raise ValueError("usage: /history [positive_number]")


def parse_sessions_limit(command: str) -> int:
    """
    从 /sessions 命令里解析出要显示多少个会话，逻辑同上。
    """
    parts = command.split()
    if len(parts) == 1:
        return SESSIONS_DEFAULT
    if len(parts) == 2 and parts[1].isdigit():
        value = int(parts[1])
        if value > 0:
            return min(value, 200)
    raise ValueError("usage: /sessions [positive_number]")


def parse_switch_session_id(command: str) -> int:
    """
    从 /switch 命令里解析出要切换到哪个会话的 ID。
    例如："/switch 3" → 返回 3。
    格式必须是 "/switch <正整数>"，否则抛出错误。
    """
    parts = command.split()
    # 必须有且仅有两段：命令 + 数字
    if len(parts) == 2 and parts[1].isdigit():
        value = int(parts[1])
        if value > 0:
            return value
    raise ValueError("usage: /switch <session_id>")


def parse_title_text(command: str) -> str:
    """
    从 /title 命令里解析出用户想设置的标题文字。
    例如："/title 今天聊了很多" → 返回 "今天聊了很多"。
    """
    # 最多分成两段："/title" 和 后面的所有内容（标题可以含空格）
    parts = command.split(" ", 1)
    if len(parts) != 2:
        raise ValueError("usage: /title <text>")
    title = parts[1].strip()   # 去掉首尾空格
    if not title:
        raise ValueError("usage: /title <text>")
    # 标题最长存 80 个字符，避免数据库字段溢出
    return title[:80]


def normalize_title(title: str | None) -> str:
    """
    把会话标题统一处理为可显示的字符串。
    如果标题是 None、空字符串、或者系统占位词（default/manual），
    统一返回 "(untitled)"，方便后续逻辑判断"这个会话有没有标题"。
    """
    if title is None:
        return "(untitled)"
    text = title.strip()
    # "default" 和 "manual" 是数据库里可能出现的占位值，也视为无标题
    if not text or text.lower() in {"default", "manual"}:
        return "(untitled)"
    return text


def should_auto_title(title: str | None) -> bool:
    """
    判断当前会话是否还没有设置标题，需要自动生成标题。
    返回 True 表示还没有标题，应该用第一句话自动命名。
    """
    # 复用 normalize_title，如果结果是 "(untitled)" 就说明没有标题
    return normalize_title(title) == "(untitled)"


def summarize_title(text: str) -> str:
    """
    把用户输入的第一句话截短，作为会话自动标题。
    例如："今天天气怎么样？" → "今天天气怎么样？"（短的不变）
         "你好，我今天遇到了一件很奇怪的事情，我想跟你说一下……" → "你好，我今天遇到了一件很奇怪的事..."
    """
    # 把多个空格/换行合并成单个空格，变成一行
    one_line = " ".join(text.strip().split())
    if not one_line:
        return "New session"
    # 超过 40 个字符就截断并加省略号，让标题保持简洁
    return one_line[:37] + "..." if len(one_line) > 40 else one_line


def build_model_messages(history_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    把数据库里读出来的历史记录，拼装成 Ollama API 需要的消息格式。
    Ollama 的 /api/chat 接口要求消息是一个列表，每项包含 role 和 content：
      [
        {"role": "system",    "content": "你是SoulMate..."},  ← 人设提示词
        {"role": "user",      "content": "你好"},             ← 用户历史消息
        {"role": "assistant", "content": "你好！有什么可以帮你的？"},  ← AI历史回复
        {"role": "user",      "content": "今天天气怎么样"},   ← 当前问题（最新）
      ]
    模型通过这个完整的历史知道"之前聊了什么"，从而实现多轮对话记忆。
    """
    # 第一条固定是 system 消息（人设），让模型知道自己要扮演谁
    payload = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 把数据库里的历史消息逐条追加进去
    # 每行只取 role（user/assistant）和 content（消息内容），忽略时间戳等其他字段
    payload.extend({"role": row["role"], "content": row["content"]} for row in history_rows)
    return payload


def show_help() -> None:
    """打印所有可用命令的说明，用户输入 /help 时调用。"""
    print("Commands:")
    print("  /help                Show command help")
    print("  /history [N]         Show latest N messages in current session (default 10)")
    print("  /sessions [N]        List recent sessions for current user (default 20)")
    print("  /switch <id>         Switch to a specific session id")
    print("  /title <text>        Set title for current session")
    print("  /new                 Create and switch to a new session")
    print("  /exit                Exit program")


def show_history(conn, session_id: int, limit: int) -> None:
    """
    从数据库读取当前会话最近 limit 条消息，打印到终端。
    用于用户输入 /history 时回顾之前聊了什么。
    """
    # 从数据库查最近 limit 条，按时间顺序返回
    rows = get_recent_messages(conn, session_id, limit=limit)
    if not rows:
        print("[info] no messages in current session.")
        return

    print(f"[history] latest {len(rows)} message(s) in session {session_id}:")
    # enumerate(..., start=1) 让序号从 1 开始而不是 0
    for i, item in enumerate(rows, start=1):
        role = item["role"]
        created_at = item.get("created_at", "")
        # 把换行替换成空格，让每条消息在一行里显示
        content = item["content"].strip().replace("\n", " ")
        # 超过 140 个字符就截断，避免终端显示太乱
        if len(content) > 140:
            content = content[:137] + "..."
        print(f"{i:02d}. [{created_at}] {role}: {content}")


def show_sessions(conn, user_id: int, current_session_id: int, limit: int) -> None:
    """
    列出该用户最近的 limit 个会话，打印到终端。
    正在使用的会话前面会有 * 标记，方便用户识别。
    """
    rows = list_user_sessions(conn, user_id=user_id, limit=limit)
    if not rows:
        print("[info] no sessions for current user.")
        return

    print(f"[sessions] latest {len(rows)} session(s):")
    for row in rows:
        sid = int(row["session_id"])
        # 当前在用的会话显示 *，其他显示空格，做成简单的"高亮"效果
        marker = "*" if sid == current_session_id else " "
        title = normalize_title(str(row["title"]))
        msg_count = int(row["message_count"])
        last_active = str(row["last_active_at"])
        created_at = str(row["created_at"])
        # :<4 表示左对齐，宽度 4，让数字列整齐对齐
        print(
            f"{marker} id={sid:<4} messages={msg_count:<4} "
            f"created={created_at} last={last_active} title={title}"
        )


def main() -> None:
    """
    程序主入口，负责：
    1. 解析命令行参数
    2. 连接数据库，确认/创建用户和会话
    3. 进入对话循环，处理用户输入（普通消息或 /xxx 命令）
    """
    # 读取命令行参数（--user、--model 等）
    args = parse_args()

    # 检测输入流是否是真实的终端（isatty）。
    # 某些远程工具（MobaXterm、VSCode Remote）会让 stdin 变成管道而非终端，
    # 这时候提前警告，避免用户困惑为什么程序突然退出。
    if not sys.stdin.isatty():
        print(
            "[warn] stdin is not an interactive TTY. "
            "Program may exit immediately if input stream closes."
        )
    # fallback_tty 是应急备用输入，正常情况下不会用到
    fallback_tty = None
    # 只警告一次"已切换到备用输入"，避免重复刷屏
    warned_fallback = False

    # 打开数据库连接，with 块结束时自动提交并关闭连接
    with get_connection() as conn:
        # 确保数据库里的表都存在（users/sessions/messages），第一次运行会自动建表
        init_schema(conn)
        # 根据用户名找到（或创建）用户记录，拿到数字 ID 用于后续查询
        user_id = get_or_create_user(conn, args.user)

        # --- 确定本次使用哪个会话 ---
        if args.session_id > 0:
            # 用户指定了 --session-id，优先用这个
            if args.new_session:
                # 同时指定了 --new-session，两者冲突，忽略 --new-session
                print("[warn] --new-session ignored because --session-id was provided.")
            if session_belongs_to_user(conn, args.session_id, user_id):
                # 确认这个会话确实属于当前用户，才允许访问
                session_id = args.session_id
            else:
                # 会话不属于该用户（防止误操作看别人的数据），降级到最近会话
                print(
                    f"[warn] session_id={args.session_id} does not belong to user={args.user}; "
                    "falling back to latest session."
                )
                # or 的意思：如果找不到最近会话（比如新用户），就新建一个
                session_id = get_latest_session_id(conn, user_id) or create_session(
                    conn, user_id, title=None
                )
        elif args.new_session:
            # 用户加了 --new-session 标志，强制开一个全新的会话
            session_id = create_session(conn, user_id, title=None)
        else:
            # 默认行为：续接上次最近的会话，没有历史就新建
            session_id = get_latest_session_id(conn, user_id) or create_session(
                conn, user_id, title=None
            )

        print(f"[ready] user={args.user} session_id={session_id} model={args.model}")
        print("Type /help to show commands.")

        # --- 单问题模式（--ask 参数）---
        if args.ask:
            # 把问题存进数据库（即使是单次提问也记录，方便以后查看）
            add_message(conn, session_id, "user", args.ask)
            # 如果会话还没有标题，就用这个问题的开头自动命名
            current_title = get_session_title(conn, session_id)
            if should_auto_title(current_title):
                update_session_title(conn, session_id, summarize_title(args.ask))
            # 读最近 12 条历史，提供上下文给模型
            history = get_recent_messages(conn, session_id, limit=12)
            messages = build_model_messages(history)
            try:
                reply = generate_reply(model=args.model, messages=messages)
            except Exception as exc:
                print(f"[error] model call failed: {exc}")
                return

            if not reply:
                print("[warn] empty response from model")
                return

            print(f"AI> {reply}")
            # 把 AI 的回答也存进数据库，保持历史完整
            add_message(conn, session_id, "assistant", reply)
            return  # 单次模式直接结束，不进入对话循环

        # --- 交互对话循环 ---
        while True:
            try:
                # 显示 "You> " 提示符，等待用户输入，去掉首尾空格
                user_text = input("You> ").strip()
            except EOFError:
                # EOF 表示输入流被关闭（比如 SSH 断开、管道结束）。
                # 尝试切换到 /dev/tty（直接连接终端设备的备用通道）继续接受输入。
                if fallback_tty is None:
                    try:
                        fallback_tty = open("/dev/tty", "r", encoding="utf-8", errors="ignore")
                    except OSError:
                        # /dev/tty 也打不开（Windows 或完全断开），只能退出
                        print(
                            "[info] input stream closed (EOF). "
                            "SSH/MobaXterm/VSCode terminal may have disconnected."
                        )
                        break
                if not warned_fallback:
                    print("[warn] stdin closed; fallback to /dev/tty input.")
                    warned_fallback = True
                # 手动打印提示符（因为已经不走 input() 了）
                sys.stdout.write("You> ")
                sys.stdout.flush()
                line = fallback_tty.readline()
                if line == "":
                    # /dev/tty 也返回空，彻底断开，退出
                    print("[info] /dev/tty input closed. Bye.")
                    break
                user_text = line.strip()
            except KeyboardInterrupt:
                # 用户按了 Ctrl+C，优雅退出
                print("\nBye.")
                break

            # 用户直接按回车（空输入），忽略，继续等待
            if not user_text:
                continue

            # --- 处理各种 /命令 ---

            if user_text == "/exit":
                print("Bye.")
                break

            if user_text == "/help":
                show_help()
                continue  # continue 表示跳过本轮剩余代码，回到循环开头等下一次输入

            if user_text == "/new":
                # 新建会话，之后的对话都记到新会话里
                session_id = create_session(conn, user_id, title=None)
                print(f"[info] switched to new session_id={session_id}")
                continue

            if user_text.startswith("/history"):
                try:
                    limit = parse_history_limit(user_text)
                except ValueError as exc:
                    print(f"[error] {exc}")
                    continue
                show_history(conn, session_id, limit)
                continue

            if user_text.startswith("/sessions"):
                try:
                    session_limit = parse_sessions_limit(user_text)
                except ValueError as exc:
                    print(f"[error] {exc}")
                    continue
                show_sessions(conn, user_id, session_id, session_limit)
                continue

            if user_text.startswith("/switch"):
                try:
                    target_session_id = parse_switch_session_id(user_text)
                except ValueError as exc:
                    print(f"[error] {exc}")
                    continue
                # 切换前验证目标会话是否属于当前用户
                if not session_belongs_to_user(conn, target_session_id, user_id):
                    print(
                        f"[error] session_id={target_session_id} not found for user={args.user}."
                    )
                    continue
                session_id = target_session_id
                title = normalize_title(get_session_title(conn, session_id))
                print(f"[info] switched to session_id={session_id} title={title}")
                continue

            if user_text.startswith("/title"):
                try:
                    new_title = parse_title_text(user_text)
                except ValueError as exc:
                    print(f"[error] {exc}")
                    continue
                updated = update_session_title(conn, session_id, new_title)
                if not updated:
                    print("[error] failed to update session title.")
                    continue
                print(f"[info] session_id={session_id} title updated.")
                continue

            # --- 普通对话流程 ---

            # 先把用户这句话存进数据库（存完再调模型，确保记录不丢失）
            add_message(conn, session_id, "user", user_text)

            # 如果会话还没有标题，用当前这句话自动生成标题
            current_title = get_session_title(conn, session_id)
            if should_auto_title(current_title):
                update_session_title(conn, session_id, summarize_title(user_text))

            # 读最近 12 条历史（含刚存的这句），让模型知道之前聊了什么
            history = get_recent_messages(conn, session_id, limit=12)
            # 拼装成 Ollama 需要的格式：[system 消息, 历史消息1, 历史消息2, ...]
            messages = build_model_messages(history)

            try:
                # 调用 Ollama，等待模型生成完整回答
                reply = generate_reply(model=args.model, messages=messages)
            except Exception as exc:
                # 模型调用失败（比如 Ollama 没启动），打印错误，继续等用户输入
                print(f"[error] model call failed: {exc}")
                continue

            if not reply:
                # 模型返回了空字符串（极少见），提示用户
                print("[warn] empty response from model")
                continue

            # 打印 AI 的回答给用户看
            print(f"AI> {reply}")
            # 把 AI 的回答也存进数据库，形成完整的对话记录
            add_message(conn, session_id, "assistant", reply)


if __name__ == "__main__":
    # 当这个文件被直接运行（而不是被其他文件 import）时，才执行 main()
    try:
        main()
    except Exception as exc:
        # 捕获所有未预期的异常，打印错误信息 + 完整调用链，方便调试
        print(f"[fatal] unexpected error: {exc}")
        traceback.print_exc()
