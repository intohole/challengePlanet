# 星轨挑战（challengePlanet）

用一句话描述你的目标，AI 自动帮你拆成可执行的每日打卡计划，并陪你坚持到底。

## 项目简介

星轨挑战是一个 AI 驱动的目标挑战与习惯养成工具。用户只需用自然语言说出想坚持的事（如"每天跑步 30 分钟"），AI 会自动解析目标、拆解生成周期性的每日任务计划，用户按日打卡完成，系统跟踪连续打卡天数、适配难度并给予积分激励。它把"立目标"变成"每天可执行的小事"，降低坚持成本。

用户可创建个人挑战或加入小队一起打卡，每日 20:00 系统自动发送打卡提醒，支持自适应难度调整、AI 引导与阶段报告，并可生成分享海报让亲友监督鼓励。

## 核心功能

- 自然语言创建挑战：AI 解析输入并流式生成每日计划，支持预览后确认
- 每日打卡与子目标：按日打卡、分解子目标、目标值/方向配置
- 签到提醒：定时任务每日 20:00 推送打卡提醒
- 积分与排行榜：积分累计、连续打卡 streak、榜单激励
- 小队协作：创建/加入小队，多人共同完成挑战
- 自适应与引导：自适应难度、AI 诊断引导、阶段报告
- 分享传播：生成分享海报与分享链接，支持导入他人挑战配置

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Python 3.13+ / FastAPI | 全量异步接口 |
| 数据访问 | SQLAlchemy 2.0 (asyncio) + aiosqlite | 异步 ORM，SQLite 持久化 |
| LLM 调用 | nexus-backend（ironman） | 统一 LLM 网关，SSE 流式 |
| 记忆 | beeMemory | 长期记忆存储 |
| 认证 | usercenter 统一登录 | nexus.get_current_user_id_required |
| 前端 | Vue 3 CDN + nexus-ui | 全局模式，静态托管 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
# 设置 UC_BASE_URL、UC_APP_KEY、UC_APP_SECRET、UC_JWT_SECRET、SERVICE_TOKEN 等

# 3. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8610
```

启动后访问 `http://localhost:8610`，接口文档见 `/docs`，健康检查见 `/health`。

## 项目结构

```
challengePlanet/
├── app/
│   ├── api/            # API 层（challenge/checkin/sub_goal/report/squad 等）
│   ├── services/       # Service 层（AI/挑战/打卡/积分/报告等）
│   ├── repositories/   # Repository 层（数据访问）
│   ├── models/         # SQLAlchemy 模型
│   ├── schemas/        # pydantic 校验模型
│   ├── db/             # 数据库管理
│   ├── core/           # 核心层（中间件）
│   ├── infra/          # 基建层（记忆客户端）
│   ├── config.py
│   └── main.py         # FastAPI 入口
├── static/             # Vue3 CDN 前端（含 login/share 海报）
├── tests/              # 端到端测试
├── minideploy.yaml
└── requirements.txt
```

## 部署

通过 miniDeploy 部署，依赖 `usercenter`、`lion`、`prompt-manager`、`beeMemory`。

| 环境变量 | 说明 |
|---------|------|
| `PORT` | 服务端口（默认 8610） |
| `UC_BASE_URL` / `UC_APP_KEY` / `UC_APP_SECRET` / `UC_JWT_SECRET` | usercenter 统一登录凭证 |
| `SERVICE_TOKEN` | 服务间调用令牌 |
| `LION_NAMESPACE` / `LION_BASE_URL` | Lion 配置中心 |
| `BEEMEMORY_BASE_URL` | beeMemory 记忆服务地址 |

## 许可证

MIT License