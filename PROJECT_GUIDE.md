# PolymarketDailyWork 项目指南

## 1. 项目简介

PolymarketDailyWork 是一个基于 FastAPI、原生 HTML 和 SQLite 的内部任务管理工具，用于管理账号月度互动计划。

系统只生成和记录人工待办任务，不会自动提交链上交易。使用时应遵守平台条款及所在地法律法规，禁止自成交、虚假交易或规避平台风控。

## 2. 主要功能

- 从 `accounts.txt` 导入账号标识。
- 每个账号每个自然月随机分配 1～2 次目标，最低要求为 1 次。
- 按“本月剩余参与次数 ÷ 本月剩余天数”动态计算每日建议量。
- 正常情况下每天生成约 1～2 个 `1对1` 任务；进度落后时自动增加，单日最多 6 个。
- 优先调度当月尚未完成首次互动的账号。
- 同一天只能生成一批任务。
- 存在未完成任务时，不允许生成下一批。
- 人工确认完成后，才会增加账号月度计数。
- 使用 `Firewall` 表保留历史配对，避免重复生成相同账号组合。
- 自然月切换时自动重置月度计数、重新分配目标，并将上月未完成任务标记为 `Expired`。
- 浏览器使用登录表单和 Session Cookie；命令行接口支持 HTTP Basic。
- 支持在管理页面查看月份、覆盖率、剩余次数、剩余天数、今日建议量和账号进度。

## 3. 项目结构

```text
PolymarketDailyWork/
├── main.py                 # FastAPI 入口、数据库、认证和调度逻辑
├── requirements.txt       # Python 依赖
├── accounts.txt            # 账号列表
├── sybil_defense.db        # SQLite 数据库，首次启动后自动创建
├── static/
│   ├── index.html          # 管理页面
│   └── login.html          # 登录页面
├── PROJECT_GUIDE.md        # 本文档
└── README.md               # 原项目说明
```

## 4. 环境要求

- Python 3.9 或更高版本，推荐 Python 3.10/3.11。
- macOS、Linux 或 Windows。
- 生产服务器推荐 Linux。
- SQLite 随 Python 标准库提供，无需单独安装。

检查 Python：

```bash
python3 --version
```

Windows PowerShell 可使用：

```powershell
python --version
```

## 5. 准备账号文件

编辑项目根目录的 `accounts.txt`，账号之间可以使用逗号、中文逗号、空格或换行分隔。

示例：

```text
101,102,103,104
105
106
```

注意：

- 正式启动前请确保文件不是空文件。
- 重复账号会自动去重。
- 新增账号会在启动时同步到数据库。
- 从文本中删除账号，不会自动删除数据库中的旧账号。
- 如果文件不存在，程序会创建内置示例账号；生产环境不要依赖示例账号。

## 6. macOS/Linux 安装全过程

进入项目目录，路径按实际位置修改：

```bash
cd /path/to/PolymarketDailyWork
```

创建虚拟环境：

```bash
python3 -m venv .venv
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

升级 pip：

```bash
python -m pip install --upgrade pip
```

安装依赖：

```bash
python -m pip install -r requirements.txt
```

确认核心依赖可以导入：

```bash
python -c "import fastapi, uvicorn, itsdangerous, multipart; print('dependencies ok')"
```

生成生产环境 Session 密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

将输出保存为环境变量：

```bash
export SESSION_SECRET='替换为上一条命令生成的随机字符串'
```

启动项目：

```bash
python main.py
```

也可以显式使用 Uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000/
```

停止项目：

```text
在启动服务的终端按 Ctrl+C
```

退出虚拟环境：

```bash
deactivate
```

## 7. Windows PowerShell 安装全过程

进入项目目录：

```powershell
cd C:\path\to\PolymarketDailyWork
```

创建虚拟环境：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻止脚本执行，可仅对当前终端临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

生成 Session 密钥：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

设置当前终端环境变量：

```powershell
$env:SESSION_SECRET="替换为生成的随机字符串"
```

启动：

```powershell
python main.py
```

浏览器访问：

```text
http://127.0.0.1:8000/
```

## 8. 登录配置

当前登录账号和密码定义在 `main.py`：

```python
ADMIN_USERNAME = "boss"
ADMIN_PASSWORD = "xxxxx"
```

部署前必须修改默认密码。不要将真实密码提交到公开 Git 仓库。

浏览器访问 `/` 时会跳转到 `/login`。登录成功后，浏览器通过 Session Cookie 调用接口。

命令行检查接口：

```bash
curl -u 'boss:你的密码' http://127.0.0.1:8000/api/status
```

## 9. 可选环境变量

程序支持以下环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SESSION_SECRET` | 开发密钥 | Session Cookie 签名密钥，生产环境必须设置 |
| `DB_FILE` | `sybil_defense.db` | SQLite 数据库路径 |
| `TXT_FILE` | `accounts.txt` | 账号文件路径 |

自定义数据库和账号文件示例：

```bash
export SESSION_SECRET='你的随机密钥'
export DB_FILE='/opt/polymarket-data/sybil_defense.db'
export TXT_FILE='/opt/polymarket-data/accounts.txt'
uvicorn main:app --host 127.0.0.1 --port 8000
```

环境变量只对当前终端生效。服务器长期运行时应写入 systemd 服务配置。

## 10. 首次启动时发生的事情

程序启动时会自动执行：

1. 创建 `Accounts`、`Tasks` 和 `Firewall` 表。
2. 检查旧数据库结构并增加缺失的月份字段。
3. 将旧版大于 2 的月目标调整为 1 或 2。
4. 根据任务日期补充历史任务月份。
5. 从 `accounts.txt` 增量导入账号。
6. 检查当前自然月并处理跨月状态。

升级不会主动删除 `Firewall` 历史配对。

旧数据库升级前仍建议备份：

```bash
cp sybil_defense.db "sybil_defense.db.backup-$(date +%Y%m%d-%H%M%S)"
```

## 11. 日常使用流程

1. 登录管理页面。
2. 查看“剩余参与次数”“本月剩余天数”和“今日建议任务”。
3. 点击“生成今日指令”。
4. 按待办列表人工完成对应操作。
5. 确认实际完成后，点击“确认已在链上完成”。
6. 系统更新账号月度计数并写入双向历史配对。
7. 当天不能再次生成新批次，下一自然日继续。

“重置本月进度”会：

- 将账号月度完成次数归零。
- 重新随机分配 1～2 次目标。
- 将当前未完成任务标记为 `Expired`。
- 保留账号数据。
- 保留历史 `Firewall` 配对。

执行重置前仍建议备份数据库。

## 12. API 列表

| 方法 | 地址 | 功能 | 认证 |
|---|---|---|---|
| `GET` | `/login` | 登录页面 | 无 |
| `POST` | `/login` | 提交登录表单 | 无 |
| `GET` | `/logout` | 清除浏览器会话 | Session |
| `GET` | `/` | 管理页面 | Session |
| `GET` | `/api/status` | 查询任务、月度计划和账号进度 | Session 或 Basic |
| `POST` | `/api/generate` | 生成今日动态任务 | Session 或 Basic |
| `POST` | `/api/complete/{task_id}` | 确认任务完成 | Session 或 Basic |
| `POST` | `/api/reset` | 重置本月进度并保留历史配对 | Session 或 Basic |

命令行生成任务：

```bash
curl -u 'boss:你的密码' -X POST http://127.0.0.1:8000/api/generate
```

命令行完成任务：

```bash
curl -u 'boss:你的密码' -X POST http://127.0.0.1:8000/api/complete/1
```

## 12.1 后台运行（nohup，最简单）

如果不需要开机自启，只想关闭 SSH 后服务继续运行，用 `nohup` 即可。

在项目目录执行：

```bash
source .venv/bin/activate
export SESSION_SECRET='你之前保存的固定密钥'
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

回车后再按一次回车回到命令行，然后就可以关闭 SSH。

查看是否运行：

```bash
ss -tlnp | grep 8000
```

查看日志：

```bash
tail -f app.log
```

停止服务：

```bash
pkill -f "uvicorn main:app"
```

说明：

- 使用 `python -m uvicorn`，避免 `uvicorn: command not found`。
- `SESSION_SECRET` 使用固定值，不要每次重新生成。
- 服务器重启后不会自动恢复，需要重新执行一次启动命令；需要自动恢复请使用下一节的 systemd。

## 13. Linux systemd 后台部署

以下示例假设：

- 项目路径为 `/opt/PolymarketDailyWork`。
- 虚拟环境为 `/opt/PolymarketDailyWork/.venv`。
- 服务用户为 `www-data`。
- Uvicorn 只监听本机 `127.0.0.1:8000`。

安装项目：

```bash
cd /opt/PolymarketDailyWork
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

创建服务文件：

```bash
sudo nano /etc/systemd/system/polymarket-daily.service
```

写入：

```ini
[Unit]
Description=PolymarketDailyWork FastAPI Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/PolymarketDailyWork
Environment="PATH=/opt/PolymarketDailyWork/.venv/bin"
Environment="SESSION_SECRET=替换为生成的随机字符串"
Environment="DB_FILE=/opt/PolymarketDailyWork/sybil_defense.db"
Environment="TXT_FILE=/opt/PolymarketDailyWork/accounts.txt"
ExecStart=/opt/PolymarketDailyWork/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

重新加载 systemd：

```bash
sudo systemctl daemon-reload
```

设置开机启动：

```bash
sudo systemctl enable polymarket-daily
```

启动服务：

```bash
sudo systemctl start polymarket-daily
```

查看状态：

```bash
sudo systemctl status polymarket-daily
```

查看实时日志：

```bash
journalctl -u polymarket-daily -f
```

重启服务：

```bash
sudo systemctl restart polymarket-daily
```

停止服务：

```bash
sudo systemctl stop polymarket-daily
```

SQLite 建议只使用一个 Uvicorn worker，不要把 `--workers 1` 改成多个 worker。

## 14. Nginx 反向代理

生产环境不建议直接将 Uvicorn 的 8000 端口暴露到公网。推荐使用 Nginx 反向代理并启用 HTTPS。

示例站点配置：

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
    }
}
```

检查配置：

```bash
sudo nginx -t
```

重新加载：

```bash
sudo systemctl reload nginx
```

配置公网服务时应继续增加 TLS/HTTPS，不要长期通过明文 HTTP 传输登录密码和 Cookie。

## 15. 更新现有服务器

停止服务：

```bash
sudo systemctl stop polymarket-daily
```

备份数据库：

```bash
cp sybil_defense.db "sybil_defense.db.backup-$(date +%Y%m%d-%H%M%S)"
```

替换程序文件后重新安装/核对依赖：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

启动并检查：

```bash
sudo systemctl start polymarket-daily
sudo systemctl status polymarket-daily
journalctl -u polymarket-daily -n 100 --no-pager
```

不要替换服务器上已有的 `sybil_defense.db` 和 `accounts.txt`，除非明确需要更换数据。

## 16. 常见问题

### 页面无法打开

检查进程和端口：

```bash
pgrep -af "uvicorn.*main:app"
ss -tlnp | grep 8000
```

### `ModuleNotFoundError: itsdangerous`

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 表单提示缺少 multipart

```bash
source .venv/bin/activate
python -m pip install "python-multipart>=0.0.6"
```

### 页面显示 0 个账号

检查 `accounts.txt` 是否为空：

```bash
cat accounts.txt
```

填写账号后重启服务：

```bash
sudo systemctl restart polymarket-daily
```

### API 返回 `Not authenticated`

浏览器需要先通过 `/login` 登录；命令行需要使用 Basic：

```bash
curl -u 'boss:你的密码' http://127.0.0.1:8000/api/status
```

### SQLite 出现锁错误

确认只运行一个 Uvicorn worker，并检查是否同时启动了多个服务进程：

```bash
pgrep -af "uvicorn.*main:app"
```

### 修改代码后页面没有变化

重启后端进程：

```bash
sudo systemctl restart polymarket-daily
```

## 17. 最简启动命令汇总

macOS/Linux 从零启动：

```bash
cd /path/to/PolymarketDailyWork
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python main.py
```

服务启动后访问：

```text
http://127.0.0.1:8000/
```
