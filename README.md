# TalkToData

基于 LangGraph 的智能数据库对话查询系统

## 项目架构

```
talktodata/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # API 路由
│   ├── core/                # 核心业务逻辑
│   ├── db/                  # 数据库连接
│   ├── graph/               # LangGraph 对话图
│   ├── models/              # 数据模型
│   └── services/            # 业务服务
├── tests/
├── requirements.txt
├── .env.example
└── config.py
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

### 3. 初始化数据库

```bash
# 初始化 PostgreSQL 元数据库
python scripts/init_meta_db.py

# 同步 MySQL schema 到 PostgreSQL
python scripts/sync_schema.py
```

#### 3.1 启动项目依赖的相关资源docker命令
- MySQL:
docker run -d --name mysql-8.4 -e MYSQL_ROOT_PASSWORD=123456 -e MYSQL_DATABASE=app -e MYSQL_USER=kodi -e MYSQL_PASSWORD=123456 -p 3307:3306 -v mysql-8.4-data:/var/lib/mysql --restart unless-stopped mysql:8.4.7

- PG:
docker run -d --name postgres-16 -e POSTGRES_PASSWORD=123456 -e POSTGRES_DB=mydb -e POSTGRES_USER=kodi -e POSTGRES_PASSWORD=123456 -p 5432:5432 -v postgres-data:/var/lib/postgresql/data --restart unless-stopped postgres:16

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 技术栈

- **对话框架**: LangGraph
- **主数据库**: MySQL (业务数据)
- **元数据库**: PostgreSQL (schema、历史、向量)
- **缓存**: Redis (会话、查询缓存)
- **API**: FastAPI
- **LLM**: OpenAI / 智谱 GLM

## 核心功能

- [ ] 自然语言转 SQL (NL2SQL)
- [ ] 多轮对话查询
- [ ] 查询结果可视化
- [ ] 查询历史管理
- [ ] Schema 语义搜索


