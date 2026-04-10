from __future__ import annotations

# os：读取环境变量，用于支持通过 SOULMATE_DB_PATH 自定义数据库位置
import os
# sqlite3：Python 内置的 SQLite 数据库驱动，不需要额外安装
import sqlite3
# Path：面向对象的路径处理，比字符串拼接更安全，跨平台兼容
from pathlib import Path
# Iterable：类型提示用，让代码读起来更清晰，运行时无影响
from typing import Iterable


# __file__ 是当前文件（sqlite_store.py）的路径。
# .parents[2] 向上跳两级：sqlite_store.py → db/ → app/ → project/
# 结果就是项目根目录，用于拼接数据库文件的路径。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 数据库默认存放位置：project/data/app.db
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"


def get_db_path() -> Path:
    """
    返回实际使用的数据库文件路径。
    优先读取环境变量 SOULMATE_DB_PATH，开发者可以在启动前设置该变量
    把数据库指向其他位置（比如测试目录）；不设置就用默认路径。
    """
    # os.getenv 读取环境变量，找不到就返回空字符串，strip() 去掉空格
    env_path = os.getenv("SOULMATE_DB_PATH", "").strip()
    if env_path:
        # expanduser() 将 ~ 展开为用户主目录，resolve() 转为绝对路径
        return Path(env_path).expanduser().resolve()
    return DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    创建并返回一个 SQLite 数据库连接。
    调用方应通过 `with get_connection() as conn:` 使用，
    with 块结束时会自动提交事务并释放连接（不需要手动 close）。
    """
    db_path = get_db_path()
    # 确保 data/ 目录存在，parents=True 表示连父目录一起创建，
    # exist_ok=True 表示目录已存在时不报错
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # timeout=30：如果数据库被其他进程锁住，最多等 30 秒再报错，
    # 防止多进程同时写入时立即崩溃
    conn = sqlite3.connect(str(db_path), timeout=30)
    # 开启外键约束（SQLite 默认关闭）。开启后，插入不存在的 user_id
    # 会报错，防止数据库里出现"孤儿数据"（找不到关联记录的消息）
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """
    建立数据库表结构（仅在表不存在时创建，不会清空已有数据）。
    程序每次启动都会调用，保证数据库结构是最新的。

    三张表的关系：
      users（用户）← sessions（会话）← messages（消息）
      一个用户可以有多个会话，每个会话可以有多条消息。
    """
    # executescript 可以一次执行多条 SQL 语句
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键，每个用户的唯一编号
            name TEXT NOT NULL UNIQUE,             -- 用户名，不允许重复
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))  -- 创建时间，自动填入本地时间
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,              -- 关联到 users 表，表示这个会话属于哪个用户
            title TEXT,                            -- 会话标题，可以为空（NULL）
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(user_id) REFERENCES users(id)  -- 外键约束：user_id 必须在 users 表中存在
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,           -- 关联到 sessions 表，表示这条消息属于哪个会话
            role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant')),
            -- role 只允许这三个值：system=系统提示词，user=用户消息，assistant=AI 回复
            -- CHECK 是数据库层的防护，写错 role 会直接报错
            content TEXT NOT NULL,                 -- 消息正文
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );

        -- 在 session_id 字段上建索引，让"查某个会话的所有消息"这个操作更快。
        -- 没有索引时每次查询要全表扫描，有索引后直接定位，数据量大时差别明显。
        CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages(session_id);
        """
    )
    # 提交事务，让建表操作真正写入磁盘（executescript 内部不自动提交）
    conn.commit()


def init_db() -> Path:
    """
    初始化数据库的便捷函数（主要供 init_db.py 脚本调用）。
    打开连接、建表、返回数据库文件路径，三步合一。
    """
    with get_connection() as conn:
        init_schema(conn)
    return get_db_path()


def get_or_create_user(conn: sqlite3.Connection, name: str) -> int:
    """
    通过用户名查找用户，返回用户 ID。
    如果用户不存在（第一次运行），自动创建后再返回 ID。
    这样外部调用不需要关心"用户存不存在"，直接拿 ID 用就行。
    """
    # ? 是占位符，防止 SQL 注入（直接拼字符串是危险的）
    row = conn.execute("SELECT id FROM users WHERE name = ?;", (name,)).fetchone()
    if row:
        return int(row[0])  # 用户已存在，直接返回 ID
    # 用户不存在，插入新用户
    cur = conn.execute("INSERT INTO users(name) VALUES(?);", (name,))
    conn.commit()
    # lastrowid 是刚插入行的自增 ID
    return int(cur.lastrowid)


def create_session(conn: sqlite3.Connection, user_id: int, title: str | None = None) -> int:
    """
    为指定用户新建一个对话会话，返回新会话的 ID。
    title 可以不传（None），之后可以通过 update_session_title 补设。
    """
    cur = conn.execute(
        "INSERT INTO sessions(user_id, title) VALUES(?, ?);",
        (user_id, title),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_latest_session_id(conn: sqlite3.Connection, user_id: int) -> int | None:
    """
    找到该用户最近一次的会话 ID（ID 最大的那个，因为 ID 是自增的，越大越新）。
    如果用户没有任何会话，返回 None，由调用方决定是否新建。
    """
    row = conn.execute(
        # ORDER BY id DESC 按 ID 倒序，LIMIT 1 只取第一条（即最新的）
        "SELECT id FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1;",
        (user_id,),
    ).fetchone()
    # 三元表达式：有结果就返回 ID，没结果（用户首次使用）就返回 None
    return int(row[0]) if row else None


def session_belongs_to_user(conn: sqlite3.Connection, session_id: int, user_id: int) -> bool:
    """
    验证某个会话是否属于当前用户。
    用于 /switch 命令：防止用户切换到别人的会话，保证数据隔离。
    """
    row = conn.execute(
        # SELECT 1 只需要知道"有没有这条记录"，不需要实际字段值，效率更高
        "SELECT 1 FROM sessions WHERE id = ? AND user_id = ? LIMIT 1;",
        (session_id, user_id),
    ).fetchone()
    # fetchone() 返回 None 表示没有匹配记录（即不属于该用户）
    return row is not None


def get_session_title(conn: sqlite3.Connection, session_id: int) -> str | None:
    """
    读取会话标题。
    返回 None 有两种情况：会话不存在，或者标题尚未设置（是 NULL）。
    """
    row = conn.execute(
        "SELECT title FROM sessions WHERE id = ? LIMIT 1;",
        (session_id,),
    ).fetchone()
    if not row:
        return None   # 会话不存在
    title = row[0]
    # title 可能是 SQL NULL（对应 Python 的 None），这里统一处理
    return str(title) if title is not None else None


def update_session_title(conn: sqlite3.Connection, session_id: int, title: str) -> bool:
    """
    更新会话标题，返回是否更新成功（True=成功，False=会话不存在）。
    """
    cur = conn.execute(
        "UPDATE sessions SET title = ? WHERE id = ?;",
        (title, session_id),
    )
    conn.commit()
    # rowcount 表示这条 UPDATE 语句实际修改了几行，
    # 如果会话 ID 不存在，rowcount 会是 0，返回 False
    return cur.rowcount > 0


def list_user_sessions(conn: sqlite3.Connection, user_id: int, limit: int = 50) -> list[dict[str, str | int]]:
    """
    列出该用户的所有会话（最新的在前），包含每个会话的消息数量和最后活跃时间。
    用于 /sessions 命令让用户看到历史会话列表。
    """
    rows = conn.execute(
        """
        SELECT
            s.id,
            s.title,
            s.created_at,
            COUNT(m.id) AS message_count,           -- 统计每个会话的消息总数
            COALESCE(MAX(m.created_at), s.created_at) AS last_active_at
            -- COALESCE 取第一个非 NULL 的值：
            -- 如果会话有消息，用最新消息的时间作为"最后活跃"；
            -- 如果会话没有消息（空会话），就用会话创建时间代替
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        -- LEFT JOIN：即使会话没有消息，也把会话本身列出来（不过滤掉空会话）
        WHERE s.user_id = ?
        GROUP BY s.id, s.title, s.created_at     -- 按会话分组，COUNT 和 MAX 才能正确计算
        ORDER BY s.id DESC                         -- 按 ID 倒序，最新的会话排在最前面
        LIMIT ?;
        """,
        # 把 limit 限制在 1~200 之间，防止传入负数或超大值
        (user_id, max(1, min(limit, 200))),
    ).fetchall()

    # 把数据库返回的元组列表转成字典列表，调用方用字段名取值更直观
    return [
        {
            "session_id": int(session_id),
            "title": str(title) if title is not None else "",
            "created_at": str(created_at),
            "message_count": int(message_count),
            "last_active_at": str(last_active_at),
        }
        for session_id, title, created_at, message_count, last_active_at in rows
    ]


def add_message(conn: sqlite3.Connection, session_id: int, role: str, content: str) -> None:
    """
    向数据库写入一条消息（用户发的或 AI 回复的）。
    role 只能是 'user' 或 'assistant'（'system' 通常不存库，只在发请求时临时加）。
    每次对话都要调用两次：一次存用户消息，一次存 AI 回复。
    """
    conn.execute(
        "INSERT INTO messages(session_id, role, content) VALUES(?, ?, ?);",
        (session_id, role, content),
    )
    # 立即提交，确保消息不因程序崩溃而丢失
    conn.commit()


def get_recent_messages(conn: sqlite3.Connection, session_id: int, limit: int = 12) -> list[dict[str, str]]:
    """
    读取指定会话最近 limit 条消息，按时间从早到晚排列，供发给模型使用。
    limit 默认 12，大约覆盖 6 轮对话（每轮 1 条用户 + 1 条 AI = 2 条）。
    """
    rows: Iterable[tuple[str, str, str]] = conn.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY id DESC    -- 先倒序取最新的 N 条（如果正序取，消息多时要全表扫描）
        LIMIT ?;
        """,
        (session_id, limit),
    ).fetchall()

    # 把元组列表转成字典列表
    items = [
        {"role": role, "content": content, "created_at": created_at}
        for role, content, created_at in rows
    ]
    # 数据库是倒序取出的（最新的在前），发给模型前要翻转回正序（最早的在前），
    # 否则模型看到的对话顺序是错的
    items.reverse()
    return items
