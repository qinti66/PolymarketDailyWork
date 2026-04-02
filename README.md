# PolymarketDailyWork（Polymarket 活跃 / 防交叉调度）

面向 **Polymarket 多账号链上活跃** 的小型内部工具：根据账号池自动生成「谁与谁交互」的待办指令，用 **防火墙图谱** 避免同一对账号重复配对，降低账号被关联（俗称「女巫」）的风险；同时按 **月配额**、**自然周配额** 控制每个钱包的参与频率。

---

## 功能概览

- **账号池**：从 `accounts.txt` 读取钱包标识（逗号分隔），同步进 SQLite；新账号会随机分配 **本月目标 3～6 次**。
- **周频**：按 **ISO 自然周** 统计；每账号每周最多 **2** 次计次（库字段 `weekly_target` 表示周上限，默认 2）；「每周至少 1 次」由运营自行排期，系统主要卡上限。
- **任务生成**：在满足月/周额度且 **历史上未配对过**（Firewall 表）的账号间随机组合，偏向 **1 对 1**。
- **完成确认**：在网页上标记任务完成后，写入双向防火墙并更新各账号计数。
- **重置**：清空任务、防火墙与计数，并按 `accounts.txt` 重新初始化（适合新月或测试）。

---

## 环境要求

- **Python 3.9+**（推荐 3.10+；使用标准库 `datetime.isocalendar()` 等）
- 操作系统：macOS / Linux / Windows 均可

---

## 依赖安装

完整清单见仓库根目录 **`requirements.txt`**（建议以文件为准）。当前包含：

| 包 | 用途 |
|----|------|
| `fastapi` | Web 框架与 API |
| `uvicorn` | ASGI 服务，运行应用 |
| `pydantic` | FastAPI 的数据校验（随 FastAPI 引入） |
| `itsdangerous` | **必装**：`SessionMiddleware` 签名会话 Cookie；部分环境不会随 Starlette 自动装上，缺了会 `ModuleNotFoundError: itsdangerous` |
| `python-multipart` | **必装**：解析表单 `Form()`（如 `/login` POST）；缺了登录提交会报错 |

另：**Starlette** 会作为 FastAPI 依赖自动安装（内含中间件等），一般无需单独写进 `requirements.txt`。

**标准库**（无需 pip）：`sqlite3`、`random`、`os`、`re`、`secrets`、`datetime`。

### 本地或服务器首次安装

```bash
cd /path/to/PolymarketDailyWork
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

### 拉取新代码后更新依赖

```bash
cd /path/to/PolymarketDailyWork
source .venv/bin/activate   # 或 venv/bin/activate
pip install -r requirements.txt
```

更新后请**重启**正在运行的 `uvicorn` / systemd 服务。

---

## 启动方式（本机）

在项目根目录、已激活虚拟环境的前提下：

```bash
python main.py
```

等价于用 Uvicorn 加载 `main:app`，默认监听 **`0.0.0.0:8000`**（本机与其它机器均可连，取决于防火墙）。本机浏览器访问：

```text
http://127.0.0.1:8000/
```

浏览器会自动跳到 **`/login` 表单登录**，成功后写入 **会话 Cookie**；管理页里的 `fetch` 会带上 Cookie，**多设备、多浏览器**均可正常使用（不再依赖「弹窗 Basic + fetch 自动带 Authorization」，避免部分浏览器只返回 `Not authenticated`）。

- **命令行 / 脚本**仍可用 **HTTP Basic**：`curl -u '账号:密码' http://.../api/status`
- **生产环境**请设置环境变量 **`SESSION_SECRET`**（足够长的随机字符串），否则服务重启后所有人需重新登录；systemd 里可写 `Environment=SESSION_SECRET=...`

也可显式使用命令行（便于改端口、写 systemd）：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

账号密码在 `main.py` 的 `ADMIN_USERNAME` / `ADMIN_PASSWORD`。

> **SQLite 说明**：当前使用单文件数据库，建议 **Uvicorn 只开 1 个 worker**（默认即可），避免多进程同时写库。

---

## 在服务器上部署与启动

下面以常见 **Linux 云服务器** 为例（已安装 Python 3）。

### 1. 上传代码并安装依赖

```bash
cd /opt   # 或你的部署目录
# 将项目放到例如 /opt/PolymarketDailyWork
cd /opt/PolymarketDailyWork
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

部署前在服务器上编辑 `main.py` 修改登录密码，并放好 `accounts.txt`（或首次运行后替换再重启）。

### 2. 放行端口

- **云厂商安全组**：入站放行 **TCP 8000**（若你改用其它端口则放行对应端口）。
- **本机防火墙**（如 `ufw`）示例：

```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

从外网访问时使用：`http://服务器公网IP:8000/`（生产环境强烈建议见下文「安全」）。

### 3. 前台 vs 后台：命令没写错，只是运行方式不同

在 SSH 里**只执行**：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

这是**前台进程**：会一直占住当前终端，`Ctrl+C` 会停服务；**关掉终端或 SSH 断线时，进程常被系统结束**，所以会感觉「没法后台」——需要改用下面 **systemd / nohup / screen** 之一。

**注意**：必须在**项目根目录**启动（与 `main.py` 同级），否则相对路径（如 `static/`、`sybil_defense.db`）会错：

```bash
cd ~/PolymarketDayWork   # 按你的实际路径改
source venv/bin/activate # 或 .venv/bin/activate
```

### 4. 前台运行（仅调试用）

```bash
cd ~/PolymarketDayWork
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
# 或: python main.py
```

断开 SSH 后进程一般会结束，只适合本机试通。

### 5. 后台常驻：systemd（推荐）

创建服务单元（路径、用户请按实际修改）：

```bash
sudo nano /etc/systemd/system/polymarket-daily.service
```

示例内容：

```ini
[Unit]
Description=PolymarketDailyWork FastAPI
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/PolymarketDailyWork
Environment="PATH=/opt/PolymarketDailyWork/.venv/bin"
Environment="SESSION_SECRET=此处换成长随机串勿泄露"
ExecStart=/opt/PolymarketDailyWork/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable polymarket-daily
sudo systemctl start polymarket-daily
sudo systemctl status polymarket-daily
```

日志：

```bash
journalctl -u polymarket-daily -f
```

### 6. 后台常驻：nohup（不配 systemd 时最快）

**一行里用 venv 里的绝对路径**，避免 `nohup` 子 shell 没激活虚拟环境：

```bash
cd ~/PolymarketDayWork
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

查看日志：`tail -f ~/PolymarketDayWork/app.log`  
查进程：`pgrep -af uvicorn`  
结束进程：`pkill -f "uvicorn main:app"`（谨慎使用）

### 7. 后台常驻：screen / tmux（临时挂着）

```bash
screen -S pm
cd ~/PolymarketDayWork && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
# 按 Ctrl+A 再按 D 脱离；恢复：screen -r pm
```

### 8. 可选：Nginx 反向代理与 HTTPS

不建议把 **仅密码保护、明文 HTTP** 的服务直接长期暴露公网。可在前面加 **Nginx**，由 Nginx 配置 TLS（Let’s Encrypt 等），再 `proxy_pass` 到 `127.0.0.1:8000`；此时 Uvicorn 可改为只监听 `127.0.0.1:8000`，由安全组只放行 443。

若仍使用 **HTTP Basic** 调后端 API（如 `curl -u`），反代需**转发认证头**，否则后端收不到密码：

```nginx
proxy_set_header Authorization $http_authorization;
```

浏览器走 **表单登录 + Cookie** 时一般不受影响，但建议仍加上，避免混用场景出问题。

---

## 检查服务是否在运行

使用 **systemd** 时（服务名按你实际修改，示例为 `polymarket-daily`）：

```bash
sudo systemctl status polymarket-daily
systemctl is-active polymarket-daily
```

未用 systemd 时，可看进程与端口：

```bash
pgrep -af "uvicorn.*main:app"
ss -tlnp | grep 8000
```

本机探活（需替换账号、密码、地址；**密码含 `@` 等特殊字符时建议用单引号**）：

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" -u '账号:完整密码' http://127.0.0.1:8000/api/status
```

- `200`：服务正常且账号密码正确  
- `401` 且 JSON 为 `无权访问防女巫中枢`：带了 Basic 但**用户名或密码与服务器 `main.py` 不一致**（请核对是否漏字符，如末尾多段）  
- `401` 且 `Not authenticated`：**未带会话 Cookie 也未带 Basic**（例如未登录就调 API）

---

## 登录与认证说明

| 方式 | 说明 |
|------|------|
| **浏览器** | 访问 `/` 会跳转到 **`/login` 表单**，登录成功后使用 **会话 Cookie**；管理页 `fetch` 使用 `credentials: 'same-origin'` 携带 Cookie，**多设备互不抢占**，各浏览器需各自登录一次。 |
| **curl / 脚本** | 使用 **HTTP Basic**：`curl -u '账号:密码' http://.../api/...` |
| **环境变量** | 生产环境设置 **`SESSION_SECRET`**（长随机串），否则重启服务后会话校验可能失效、全员需重新登录；**不要**把密钥写进公开仓库。 |

退出登录：浏览器访问 **`/logout`**（管理页有「退出登录」链接）。

---

## 常见问题与排错

1. **`ModuleNotFoundError: No module named 'itsdangerous'`**  
   执行 `pip install -r requirements.txt` 或 `pip install "itsdangerous>=2.1.2"`，然后重启进程。

2. **登录表单提交失败 / 提示与 multipart 相关**  
   执行 `pip install "python-multipart>=0.0.6"` 或整表重装 `pip install -r requirements.txt`，重启服务。

3. **浏览器里接口返回 `Not authenticated`，但 `curl -u` 正常**  
   多为未走表单登录或 Cookie 未带上：先打开 **`/login`** 登录；若前面有 Nginx，确认配置里包含 `proxy_set_header Authorization $http_authorization;`（见上文）。

4. **`curl` 返回 401，`detail` 为 `无权访问防女巫中枢`**  
   说明请求已带 Basic，但**密码或账号与服务器上 `main.py` 不一致**（请复制服务器上的完整密码，注意密码中 `@@` 等字符不要截断）。

5. **SSH 断开后服务没了**  
   你用的是前台 `uvicorn`；请改用本文 **nohup、systemd 或 screen**（见「在服务器上部署与启动」各小节）。

---

## 目录与数据文件

| 路径 | 说明 |
|------|------|
| `main.py` | 后端入口、业务逻辑、鉴权与常量 |
| `static/index.html` | 管理页前端 |
| `static/login.html` | 表单登录页 |
| `requirements.txt` | Python 依赖（含 `itsdangerous`、`python-multipart` 等） |
| `accounts.txt` | 账号列表（逗号分隔）；不存在时会用代码内兜底串创建 |
| `sybil_defense.db` | SQLite 数据库（运行后自动生成） |

---

## 配置说明（部署前必看）

1. **修改登录密码**：编辑 `main.py` 中的 `ADMIN_USERNAME`、`ADMIN_PASSWORD`，勿将默认密码提交到公开仓库。
2. **账号列表**：维护 `accounts.txt`，与 Polymarket 侧使用的钱包标识一致即可（格式为逗号分隔的 ID）。
3. **月/周区间**：可在 `main.py` 中调整 `MONTHLY_TARGET_MIN` / `MONTHLY_TARGET_MAX`、`WEEKLY_INTERACTION_MIN` / `WEEKLY_INTERACTION_MAX` 等常量；单账号周上限也可在数据库 `Accounts.weekly_target` 中按需修改（详见代码注释）。
4. **会话密钥**：生产环境设置环境变量 **`SESSION_SECRET`**（与 systemd `Environment=` 或 shell `export` 均可）。

---

## 路由与 API 说明

**受保护资源**（未登录且无 Basic 时返回 `401`）：首页 `/`、所有 `/api/*`。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/login` | 表单登录页（无需先登录） |
| `POST` | `/login` | 提交用户名、密码，成功则写会话并跳转 `/` |
| `GET` | `/logout` | 清除会话，跳转登录页 |
| `GET` | `/` | 管理页（需会话或 Basic） |
| `GET` | `/api/status` | 待办任务、账号月/周进度、当前 ISO 周等 |
| `POST` | `/api/generate` | 生成一批新任务（有待办时不会重复生成） |
| `POST` | `/api/complete/{task_id}` | 标记任务完成并更新防火墙与计数 |
| `POST` | `/api/reset` | 清空库并按 `accounts.txt` 重建账号行 |

浏览器使用 **Cookie 会话**；命令行可使用 **HTTP Basic**（`curl -u`）。

---

## 免责声明

本工具仅用于 **合法合规** 的多账号运营与内部协作记录；请遵守 Polymarket 及当地法律法规。作者不对使用方式与后果承担责任。
