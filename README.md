# customer-service 电商智能客服系统（客服服务）

商城的智能客服系统。本仓库是其中的**客服服务**：负责会话、消息、AI 轮次调度、人工转接和实时推送，是用户端、管理端与 AI 服务之间的消息中枢。

## 系统全景

整个系统由 2 个前端 + 3 个后端服务组成，本仓库只包含客服服务，其余服务不在本仓库内：

| 应用 | 端口 | 职责 | 在本仓库 |
|---|---|---|---|
| 用户端（Vue） | 5173 | 商品、订单、客服会话、用户确认操作 | 否 |
| 管理端（Vue） | 5174 | 人工客服工作台、运行情况查看 | 否 |
| 客服服务（本仓库） | 8000 | 会话、消息、轮次、人工工单、实时推送 | **是** |
| 电商服务 | 8001 | 用户、商品、订单、物流、售后（业务事实源） | 否 |
| AI 服务 | 8002 | 理解问题、查数据/知识、生成并校验回复 | 否（仓库内有 `mock_ai` 可临时顶替） |

核心约定：

- AI 只负责理解和生成，**不直接改业务数据**；取消订单、改地址等操作由 AI 给出页面动作，用户在页面确认后由电商服务执行。
- 客服服务不直接调用电商服务；商品、订单等事实数据由前端直查电商服务，AI 服务的工具以用户身份调用电商服务。
- 聊天数据以 PostgreSQL 为最终存储；Redis 只做 Pub/Sub 实时分发，不存聊天记录。

## 技术栈

- Python ≥ 3.12，FastAPI + Uvicorn
- SQLAlchemy 2（异步）+ psycopg 3，数据库 PostgreSQL
- Redis（`redis.asyncio`）Pub/Sub + WebSocket 实时推送
- PyJWT 令牌校验（HS256，与电商、AI 服务共用同一密钥）
- httpx 异步调用 AI 服务
- Pydantic / pydantic-settings 做请求校验与配置管理
- 包管理：uv

## 功能概览

- **会话与消息**：按用户复用未关闭会话；AI 模式会话空闲 30 分钟自动关闭；消息按 `message_id` 幂等去重
- **AI 轮次调度**：用户连发消息在 800ms 窗口内合并为一个轮次；Worker 领取轮次时拍消息快照，AI 处理期间的新消息会使旧结果作废（SUPERSEDED）；调用失败最多重试 3 次，超限给出兜底回复
- **人工转接**：AI 提议或用户主动申请转人工后生成工单（排队 → 接单 → 结束），客服在管理端接入原会话，用户无需重复描述问题；接单用行锁防多人抢单
- **实时推送**：业务数据与待推送事件同事务落库（发件箱），Realtime Worker 发布到 Redis，服务再经 WebSocket 推给前端；断线漏掉的消息由历史接口补齐
- **管理统计**：会话总数、工单总数、排队中数、人工中数

## 目录结构

```
cs/
├── main.py                  # 8000 服务启动入口（自定义事件循环 + uvicorn）
├── app/
│   ├── app.py               # FastAPI 组装：注册路由、Swagger 鉴权、CORS
│   ├── dependencies.py      # 依赖注入：会话、服务、用户/客服/管理员身份
│   ├── schemas.py           # 请求模型与 CurrentUser
│   ├── models/              # ORM 模型与枚举（会话/消息/轮次/实时事件/工单）
│   ├── routers/             # 接口层：chat / realtime(WebSocket) / admin
│   └── services/            # 业务层：chat / realtime / admin(工单) / auth(令牌)
├── worker/
│   ├── ai.py                # AI Worker：领轮次 → 调 AI 服务 → 结算（独立进程）
│   └── realtime.py          # Realtime Worker：发布发件箱事件到 Redis（独立进程）
├── infrastructure/
│   ├── db.py                # 异步引擎与会话工厂
│   ├── redis.py             # Redis 客户端
│   └── init_db.py           # 建表脚本（单独运行）
├── common/
│   ├── settings.py          # 配置（读项目根目录 .env，带缓存）
│   ├── event_loop.py        # SelectorEventLoop 事件循环工厂
│   └── utils.py             # UTC 时间、带前缀的业务 ID 生成
├── mock_ai/
│   └── app.py               # 假 AI 服务（8002）：关键词触发固定回复/转人工
└── test/
    └── orm.py               # ORM 操作演示（非自动化测试）
```

## 快速开始

### 1. 前置条件

- Python ≥ 3.12，已安装 uv
- 可用的 PostgreSQL 和 Redis（本地或虚拟机均可，地址在 `.env` 中配置）
- 电商服务（8001）与 AI 服务（8002）如需完整链路需另行启动；只验证客服链路时可用仓库内 `mock_ai` 顶替 8002

### 2. 安装依赖

```bash
uv sync
```

### 3. 配置 .env

复制 `.env.example` 为项目根目录的 `.env`，按实际环境修改。只列字段名与用途，**不要把真实令牌提交进仓库**（确认 `.env` 已在 `.gitignore` 中）：

| 配置 | 用途 |
|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 |
| `REDIS_URL` | Redis 地址 |
| `AI_SERVICE_URL` | AI 服务地址（默认 `http://127.0.0.1:8002`） |
| `CORS_ORIGINS` | 允许的前端来源（5173 / 5174） |
| `JWT_SECRET` / `JWT_ALGORITHM` | 用户令牌校验密钥与算法，必须与电商、AI 服务一致 |
| `INTERNAL_SERVICE_TOKEN` | 服务间内部调用令牌 |
| `MESSAGE_MERGE_DELAY_MS` | 轮次消息合并窗口（默认 800） |
| `CONVERSATION_IDLE_TIMEOUT_MINUTES` | AI 会话空闲超时（默认 30） |
| `AI_TIMEOUT_SECONDS` | 调用 AI 服务超时（默认 30，连接 5 秒） |
| `AI_WORKER_PULL_INTERVAL_MS` | AI Worker 轮询间隔（默认 100） |
| `AI_WORKER_MAX_ATTEMPTS` | 轮次重试上限（默认 3） |

### 4. 建表（首次运行）

```bash
uv run python -m cs.infrastructure.init_db
```

> ⚠️ 该脚本会先 `drop_all` 再 `create_all`，**重复运行会清空已有聊天数据**，只在首次部署或确认要重建时运行。

### 5. 按顺序启动进程

客服服务全链路共 4 个进程，需分别在不同终端启动，缺一个链路就断在对应环节：

```bash
# 终端 1：假 AI 服务（已有真 AI 服务时跳过，改为启动真服务于 8002）
uv run python -m cs.mock_ai.app

# 终端 2：客服服务主进程（8000）
uv run python -m cs.main

# 终端 3：AI Worker（领轮次、调 AI、落回复）
uv run python -m cs.worker.ai

# 终端 4：Realtime Worker（把发件箱事件发布到 Redis）
uv run python -m cs.worker.realtime
```

启动后打开 `http://127.0.0.1:8000/docs`，能看到接口列表并可带令牌在线调试，即主服务已就绪。

## 接口一览（客服服务，前缀 `/api/v1`）

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/chat/messages` | 发送一条聊天消息（幂等去重、建/复用轮次） | user |
| GET | `/chat/history` | 获取当前会话与该用户全部历史消息 | user |
| WS | `/realtime` | 实时推送长连接，连上后首帧发送 `{"token": "<令牌>"}` | user / staff |
| GET | `/handoffs` | 未结束工单列表 | staff |
| GET | `/handoffs/{id}/messages` | 某工单对应会话的全部消息 | staff |
| POST | `/handoffs/{id}/accept` | 接单（会话切人工模式） | staff |
| POST | `/handoffs/{id}/messages` | 人工客服回复 | staff |
| POST | `/handoffs/{id}/resolve` | 结单（会话切回 AI 模式） | staff |
| GET | `/admin/metrics` | 运行统计：会话/工单/排队/人工数量 | admin |

鉴权方式：HTTP 接口在请求头带 `Authorization: Bearer <令牌>`。令牌由电商服务登录签发，客服服务只验令牌中的 `user_id` 与 `role`；无令牌或令牌无效返回 401，身份有效但角色不符返回 403。

## 一条消息的完整链路

1. 用户在前端发送消息，前端 POST 到 `/chat/messages`，客服服务去重后落库
2. AI 模式下消息进入一个 `COLLECTING` 轮次，800ms 内连发的消息合并进同一轮次
3. AI Worker 领取到期轮次，拍下当前最新消息位置作为快照，组装本轮消息 + 最近 30 条历史
4. Worker 带用户令牌与内部令牌调用 AI 服务 `/internal/v1/agent/runs`
5. AI 返回结构化结果（回答 / 澄清 / 拒绝 / 转人工）；结算时先校验快照，期间有新消息则旧结果作废
6. 回复落库的同时写一条实时事件，Realtime Worker 发布到 Redis，服务经 WebSocket 推给前端
7. 若结果为转人工，则生成工单、会话切排队模式，客服在管理端接单后进入人工对话

## 数据模型

| 表 | 说明 |
|---|---|
| `conversations` | 会话：归属用户、接待模式（AI / QUEUED / HUMAN / CLOSED）、最后活跃时间 |
| `messages` | 消息：所属会话、角色（USER / AI / HUMAN）、类型与 JSONB 内容、业务 `message_id` |
| `conversation_turns` | AI 轮次：状态（COLLECTING / RUNNING / COMPLETED / SUPERSEDED / FAILED）、收集截止、消息快照、尝试次数 |
| `realtime_events` | 实时事件（发件箱）：推送目标、负载、发布时间（为空表示未发布） |
| `handoffs` | 人工工单：所属会话、摘要、状态（WAITING / ACTIVE / RESOLVED）、接单客服 |

关键约束由数据库兜底（局部唯一索引）：单用户至多一个未关闭会话、单会话至多一个 COLLECTING 与一个 RUNNING 轮次、单会话至多一张未结束工单。

## 常见问题

- **页面一直显示“AI 正在处理”**：多半是 AI Worker 没启动。消息落库和建轮次只代表已排队，领轮次、调 AI、落回复是 AI Worker 进程的活。
- **发了消息前端没动静**：检查 Realtime Worker 是否启动、Redis 地址是否可达；WebSocket 是否已连接（后端日志有 `connection open`）。
- **启动报端口占用（WinError 10048）**：8000 已被旧进程占用，先查 PID 关闭旧进程再重启。
- **接口返回 401 / 403**：401 是令牌缺失、无效或密钥与签发方不一致；403 是令牌有效但角色不满足该接口要求。
- **改了 .env 没生效**：配置在首次读取后有缓存，需重启进程；另外 `cs/infrastructure/redis.py` 的地址如与 `.env` 不一致，以代码中实际使用的为准排查。
