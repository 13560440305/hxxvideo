# StarVoyage — 启动指南

## 环境要求

- Python 3.12+
- Node.js 20+
- FFmpeg（PATH 或 config.yaml 中配置路径）
- PostgreSQL 15+（含 pgvector 扩展）
- Redis 7+

---

## 1. 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd web/frontend && npm install && cd ../..
```

## 2. 配置

```bash
# 复制示例配置，填入 API Key
cp config-example.yaml config.yaml
# 编辑 config.yaml，填入 OPENROUTER_API_KEY 和 SILICONFLOW_API_KEY
```

## 3. 初始化数据库

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE starvoyage;"
psql -U postgres -d starvoyage -c "CREATE EXTENSION vector;"

# 初始化表结构
python -m src init-db
```

## 4. 启动

### 方式 A：本地开发（双终端）

**终端 1 — FastAPI 后端：**
```bash
cd d:\curProject\h2x\hxxvideo
uvicorn web.backend.main:app --reload --port 8000
# API 地址: http://127.0.0.1:8000
# API 文档: http://127.0.0.1:8000/docs
```

**终端 2 — Next.js 前端：**
```bash
cd d:\curProject\h2x\hxxvideo\web\frontend
npm run dev
# 浏览器打开: http://localhost:3000
```

### 方式 B：Docker 部署

```bash
cd d:\curProject\h2x\hxxvideo\web
docker compose up
```

### 方式 C：仅 CLI（不需要 Web）

```bash
python -m src run --topic "成都火锅" --niche china_food --duration 60
```

## 5. 验证

```bash
# API 健康检查
curl http://127.0.0.1:8000/api/health
# → {"status":"ok"}

# 查看可用模板
curl http://127.0.0.1:8000/api/niches
```

## 6. 常见问题

**后端启动报数据库连接错误：**
- 确认 PostgreSQL 已启动
- 确认 `config.yaml` 中数据库密码正确
- 可加 `--no-db` 参数跳过数据库

**前端请求跨域：**
- FastAPI 已开启 CORS，默认允许所有来源
- 确保 `NEXT_PUBLIC_API_URL` 指向正确的后端地址

**FFmpeg 找不到：**
- 编辑 `config.yaml` 中的 `paths.ffmpeg_path`，填入你的 FFmpeg 路径
- 或将 FFmpeg 所在目录加入系统 PATH
