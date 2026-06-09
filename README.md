# TalkToData

基于 LangGraph 的智能数据库对话查询系统

## 项目架构

```
talktodata/
├── app/                    # 后端服务 (FastAPI)
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # API 路由
│   ├── conf/                # 配置管理
│   ├── db/                  # 数据库连接
│   ├── graph/               # LangGraph 对话图
│   ├── models/              # 数据模型
│   └── services/            # 业务服务
├── frontend/                # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── components/      # Vue 组件
│   │   ├── views/           # 页面视图
│   │   └── main.ts          # 入口文件
│   ├── package.json
│   └── vite.config.ts
├── tests/
├── requirements.txt
└── .env.example
```

## 快速开始

### 一、后端服务

#### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

主要配置项：
```env
# LLM 配置
qwen_api_key=your_api_key_here
qwen_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
qwen_model_name=qwen-plus-2025-12-01

# MySQL 配置
mysql_host=localhost
mysql_port=3307
mysql_user=kodi
mysql_password=123456
mysql_database=app

# PostgreSQL 配置
pg_host=localhost
pg_port=5432
pg_user=kodi
pg_password=123456
pg_database=ttd
```

#### 3. 启动项目依赖的 Docker 服务

```bash
# MySQL
docker run -d --name mysql-8.4 \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -e MYSQL_DATABASE=app \
  -e MYSQL_USER=kodi \
  -e MYSQL_PASSWORD=123456 \
  -p 3307:3306 \
  -v mysql-8.4-data:/var/lib/mysql \
  --restart unless-stopped mysql:8.4.7

# PostgreSQL
docker run -d --name postgres-16 \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=ttd \
  -e POSTGRES_USER=kodi \
  -p 5432:5432 \
  -v postgres-data:/var/lib/postgresql/data \
  --restart unless-stopped postgres:16
```

# ES
docker run -d --name es8 --hostname es8-node -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" -e "xpack.security.enabled=false" -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" -v es8-data:/usr/share/elasticsearch/data docker.elastic.co/elasticsearch/elasticsearch:8.19.9



# kibana
docker run -d \
  --name kibana \
  --link es8:elasticsearch \
  -p 5601:5601 \
  -e "ELASTICSEARCH_HOSTS=http://elasticsearch:9200" \
  docker.elastic.co/kibana/kibana:8.19.9


#### 4. 启动后端服务

```bash
# 方式一：直接运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式二：使用 Python
python -m app.main
```

后端 API 文档：http://localhost:8000/docs

---

### 二、前端应用

#### 1. 安装 Node.js 依赖

```bash
cd frontend
npm install
```

#### 2. 配置 API 地址

编辑 `frontend/.env.development`，设置后端 API 地址：
```env
VITE_API_BASE_URL=http://localhost:8000
```

生产环境配置 `frontend/.env.production`：
```env
VITE_API_BASE_URL=https://your-api-domain.com
```

#### 3. 启动前端开发服务器

```bash
npm run dev
```

前端访问地址：http://localhost:5173

#### 4. 构建生产版本

```bash
npm run build
```

构建产物在 `frontend/dist` 目录。

---

## 技术栈

### 后端
- **对话框架**: LangGraph
- **Web 框架**: FastAPI
- **主数据库**: MySQL (业务数据)
- **元数据库**: PostgreSQL (schema、历史、事件)
- **ORM**: SQLAlchemy (异步)
- **LLM**: 智谱 GLM / OpenAI

### 前端
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI 组件**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router
- **HTTP 客户端**: Axios
- **Markdown**: markdown-it
- **代码高亮**: highlight.js
- **SQL 预览**: sql.js

## 核心功能

- [x] 自然语言转 SQL (NL2SQL)
- [x] 多轮对话查询
- [x] 查询结果可视化
- [x] 查询历史管理
- [x] 实时流式响应
- [x] 高并发支持

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/chat/stream` | POST | 流式对话查询 |
| `/chat/query` | POST | 非流式对话查询 |
| `/chat/sessions` | POST | 创建会话 |
| `/chat/sessions/{id}` | GET | 获取会话信息 |
| `/chat/sessions/{id}/messages` | GET | 获取会话消息历史 |
| `/health` | GET | 健康检查 |

