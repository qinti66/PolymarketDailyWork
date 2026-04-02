import sqlite3
import random
import os
import re
import secrets
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

app = FastAPI()

# ==========================================
# 0. 🔐 安全防护配置 (部署前请务必修改密码)
# ==========================================
ADMIN_USERNAME = "boss"               # 网页登录账号
ADMIN_PASSWORD = "xxxxx" # 网页登录密码
# 会话密钥：生产务必设置环境变量 SESSION_SECRET（稳定、足够长）；否则每次改代码默认串需一致
SESSION_SECRET = os.environ.get("SESSION_SECRET") or (
    "DEV_ONLY_set_SESSION_SECRET_env_in_production_min32chars!"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)

security_optional = HTTPBasic(auto_error=False)


def verify_auth(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security_optional),
):
    """浏览器：登录页写入 session 后，fetch 需 credentials:'include' 带 Cookie。
    命令行：仍可用 curl -u 走 HTTP Basic。"""
    sess = request.session.get("user")
    if sess is not None and secrets.compare_digest(str(sess), ADMIN_USERNAME):
        return ADMIN_USERNAME
    if credentials is not None:
        u_ok = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
        p_ok = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
        if u_ok and p_ok:
            return credentials.username
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无权访问防女巫中枢",
            headers={"WWW-Authenticate": "Basic"},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

# ==========================================
# 1. 数据库与数据初始化
# ==========================================
DB_FILE = "sybil_defense.db"
TXT_FILE = "accounts.txt"
# 你的70个账号兜底数据
DEFAULT_ACCOUNTS = "363,364,365,366,367,368,369,370,371,372,373,374,375,376,377,378,379,380,381,382,383,384,385,386,387,388,389,390,391,392,393,394,395,396,397,398,399,400,401,402,423,424,425,426,427,428,429,430,431,432,433,434,435,436,437,438,439,440,441,442,21,22,23,24,25,26,27,28,29,30"

# 月：每账号随机目标 ∈ [3,6]；周：每自然周完成次数 ∈ [1,2]（系统只卡「上限 2」，「至少 1」为运营口径）
MONTHLY_TARGET_MIN = 3
MONTHLY_TARGET_MAX = 6
WEEKLY_INTERACTION_MIN = 1
WEEKLY_INTERACTION_MAX = 2
# 库列 weekly_target 表示「每周次数上限」，默认 2，可按账号改小为 1（更严）
WEEKLY_CAP_DEFAULT = WEEKLY_INTERACTION_MAX


def iso_week_key() -> str:
    y, w, _ = datetime.now().isocalendar()
    return f"{y}-W{w:02d}"


def sync_account_weeks(conn):
    """ISO 周切换时清零本周计数；首次写入 week_key。"""
    wk = iso_week_key()
    c = conn.cursor()
    c.execute(
        "UPDATE Accounts SET week_current = 0, week_key = ? WHERE IFNULL(week_key, '') != ?",
        (wk, wk),
    )
    conn.commit()


def migrate_accounts_schema():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA table_info(Accounts)")
    col_names = {row[1] for row in c.fetchall()}
    if "weekly_target" not in col_names:
        c.execute("ALTER TABLE Accounts ADD COLUMN weekly_target INTEGER DEFAULT 2")
    if "week_current" not in col_names:
        c.execute("ALTER TABLE Accounts ADD COLUMN week_current INTEGER DEFAULT 0")
    if "week_key" not in col_names:
        c.execute("ALTER TABLE Accounts ADD COLUMN week_key TEXT DEFAULT ''")
    c.execute(
        "UPDATE Accounts SET target_count = ? WHERE target_count < ?",
        (MONTHLY_TARGET_MIN, MONTHLY_TARGET_MIN),
    )
    c.execute(
        "UPDATE Accounts SET target_count = ? WHERE target_count > ?",
        (MONTHLY_TARGET_MAX, MONTHLY_TARGET_MAX),
    )
    c.execute(
        "UPDATE Accounts SET weekly_target = ? WHERE IFNULL(weekly_target, 0) < ?",
        (WEEKLY_CAP_DEFAULT, WEEKLY_INTERACTION_MIN),
    )
    # 旧版 weekly_target=1 表示「满 1 次即出队」，现列含义为「每周次数上限」，统一为 2
    c.execute(
        "UPDATE Accounts SET weekly_target = ? WHERE weekly_target = 1",
        (WEEKLY_CAP_DEFAULT,),
    )
    c.execute(
        "UPDATE Accounts SET weekly_target = ? WHERE weekly_target > ?",
        (WEEKLY_INTERACTION_MAX, WEEKLY_INTERACTION_MAX),
    )
    conn.commit()
    conn.close()


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS Accounts (
            acc_id TEXT PRIMARY KEY,
            target_count INTEGER,
            current_count INTEGER,
            weekly_target INTEGER NOT NULL DEFAULT 2,
            week_current INTEGER NOT NULL DEFAULT 0,
            week_key TEXT NOT NULL DEFAULT ''
        )"""
    )
    c.execute('''CREATE TABLE IF NOT EXISTS Tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, source TEXT, targets TEXT, task_type TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS Firewall (source TEXT, target TEXT, UNIQUE(source, target))''')
    conn.commit()
    conn.close()
    migrate_accounts_schema()

def load_accounts_from_txt():
    if not os.path.exists(TXT_FILE):
        with open(TXT_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_ACCOUNTS)
            
    with open(TXT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = re.sub(r'[，,\n\t\s]+', ',', content)
    raw_accounts = [acc.strip() for acc in content.split(',') if acc.strip()]
    unique_accounts = list(set(raw_accounts))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for acc in unique_accounts:
        c.execute("SELECT acc_id FROM Accounts WHERE acc_id=?", (acc,))
        if not c.fetchone():
            monthly = random.randint(MONTHLY_TARGET_MIN, MONTHLY_TARGET_MAX)
            c.execute(
                """INSERT INTO Accounts (acc_id, target_count, current_count, weekly_target, week_current, week_key)
                   VALUES (?, ?, 0, ?, 0, '')""",
                (acc, monthly, WEEKLY_CAP_DEFAULT),
            )
    conn.commit()
    conn.close()

def reset_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS Accounts")
    c.execute("DROP TABLE IF EXISTS Tasks")
    c.execute("DROP TABLE IF EXISTS Firewall")
    conn.commit()
    conn.close()
    init_db()
    load_accounts_from_txt()

def generate_today_tasks(num_tasks=4):
    conn = sqlite3.connect(DB_FILE)
    sync_account_weeks(conn)
    c = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT count(*) FROM Tasks WHERE status='Pending'")
    if c.fetchone()[0] > 0:
        conn.close()
        return "当前还有未完成的任务，请先执行完毕。"

    c.execute(
        """SELECT acc_id FROM Accounts
           WHERE current_count < target_count
             AND week_current < COALESCE(weekly_target, ?)""",
        (WEEKLY_CAP_DEFAULT,),
    )
    available_accs = [row[0] for row in c.fetchall()]
    if len(available_accs) < 2:
        conn.close()
        return "可用账号不足（本月已满，或本周已达周次数上限），任务矩阵暂无法继续展开。"
        
    random.shuffle(available_accs)
    c.execute("SELECT source, target FROM Firewall")
    history = set(f"{row[0]}_{row[1]}" for row in c.fetchall())
    
    tasks_created = 0
    while available_accs and tasks_created < num_tasks:
        if len(available_accs) < 2: break
        source = available_accs.pop(0)
        
        # 核心防女巫策略：60% 概率维持在绝对安全的 1对1 交互
        max_targets = random.choices([1, 2, 3, 4], weights=[60, 25, 10, 5], k=1)[0]
        targets, temp_pool = [], []
        
        while available_accs and len(targets) < max_targets:
            candidate = available_accs.pop(0)
            # 绝对无环图谱校验
            if f"{source}_{candidate}" not in history and f"{candidate}_{source}" not in history:
                targets.append(candidate)
                history.add(f"{source}_{candidate}")
                history.add(f"{candidate}_{source}") 
            else:
                temp_pool.append(candidate)
        available_accs.extend(temp_pool)
        
        if targets:
            c.execute("INSERT INTO Tasks (date, source, targets, task_type, status) VALUES (?, ?, ?, ?, 'Pending')",
                      (today_str, source, ",".join(targets), f"1对{len(targets)}"))
            tasks_created += 1
            
    conn.commit()
    conn.close()
    return f"成功生成 {tasks_created} 个防交叉调度指令。"

# ==========================================
# 2. 🛡️ 带密码保护的 RESTful API 接口
# ==========================================
@app.on_event("startup")
def startup_event():
    init_db()
    load_accounts_from_txt()

@app.get("/api/status", dependencies=[Depends(verify_auth)])
def api_status():
    conn = sqlite3.connect(DB_FILE)
    sync_account_weeks(conn)
    c = conn.cursor()
    c.execute("SELECT id, date, source, targets, task_type FROM Tasks WHERE status='Pending'")
    pending_tasks = c.fetchall()
    
    c.execute(
        "SELECT acc_id, current_count, target_count, week_current, weekly_target FROM Accounts"
    )
    rows = c.fetchall()
    stats = [
        {
            "acc_id": r[0],
            "month_current": r[1],
            "month_target": r[2],
            "week_current": r[3],
            "week_cap": r[4] if r[4] is not None else WEEKLY_CAP_DEFAULT,
            "week_min": WEEKLY_INTERACTION_MIN,
            "week_max": WEEKLY_INTERACTION_MAX,
        }
        for r in rows
    ]
    try:
        stats.sort(
            key=lambda x: (0, int(x["acc_id"])) if str(x["acc_id"]).isdigit() else (1, x["acc_id"])
        )
    except Exception:
        stats.sort(key=lambda x: str(x["acc_id"]))
        
    total_accs = len(stats)
    completed_accs = sum(1 for s in stats if s["month_current"] >= s["month_target"])
    conn.close()
    
    return {
        "total_accs": total_accs,
        "completed_accs": completed_accs,
        "pending_tasks": pending_tasks,
        "stats": stats,
        "iso_week": iso_week_key(),
        "month_min": MONTHLY_TARGET_MIN,
        "month_max": MONTHLY_TARGET_MAX,
        "week_min": WEEKLY_INTERACTION_MIN,
        "week_max": WEEKLY_INTERACTION_MAX,
    }

@app.post("/api/generate", dependencies=[Depends(verify_auth)])
def api_generate():
    return {"message": generate_today_tasks(num_tasks=random.randint(3, 6))}

def bump_account_task_completion(conn, c, acc_id: str):
    wk = iso_week_key()
    c.execute(
        "SELECT IFNULL(week_key, ''), IFNULL(week_current, 0) FROM Accounts WHERE acc_id=?",
        (acc_id,),
    )
    row = c.fetchone()
    if not row:
        return
    stored_wk, wc = row[0], int(row[1])
    if stored_wk != wk:
        wc = 0
    c.execute(
        """UPDATE Accounts SET current_count = current_count + 1,
               week_current = ?, week_key = ? WHERE acc_id=?""",
        (wc + 1, wk, acc_id),
    )


@app.post("/api/complete/{task_id}", dependencies=[Depends(verify_auth)])
def api_complete(task_id: int):
    conn = sqlite3.connect(DB_FILE)
    sync_account_weeks(conn)
    c = conn.cursor()
    c.execute("SELECT source, targets, status FROM Tasks WHERE id=?", (task_id,))
    task = c.fetchone()
    if not task or task[2] == 'Completed':
        return {"status": "error", "message": "任务已完成或不存在"}
    
    source = task[0]
    targets = [x.strip() for x in task[1].split(",") if x.strip()]
    
    # 写入防火墙，双向彻底封死后续交互可能
    for t in targets:
        c.execute("INSERT OR IGNORE INTO Firewall (source, target) VALUES (?, ?)", (source, t))
        c.execute("INSERT OR IGNORE INTO Firewall (source, target) VALUES (?, ?)", (t, source))
        bump_account_task_completion(conn, c, t)
        
    bump_account_task_completion(conn, c, source)
    c.execute("UPDATE Tasks SET status='Completed' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/reset", dependencies=[Depends(verify_auth)])
def api_reset():
    reset_database()
    return {"message": "✅ 数据库已抹除，本月/本周配额与防交叉记录已重置！"}

# ==========================================
# 3. 🛡️ 前端路由拦截与分发
# ==========================================
@app.get("/login")
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/", status_code=302)
    if not os.path.exists("static/login.html"):
        raise HTTPException(status_code=404, detail="缺少 static/login.html")
    return FileResponse("static/login.html")


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(),
    password: str = Form(),
):
    if secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(
        password, ADMIN_PASSWORD
    ):
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?err=1", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/")
def serve_frontend(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=302)
    if not os.path.exists("static/index.html"):
        raise HTTPException(status_code=404, detail="前端文件 static/index.html 丢失，请检查目录结构。")
    return FileResponse("static/index.html")

if __name__ == "__main__":
    # host="0.0.0.0" 允许外网访问服务器
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)