# StarVoyage AI Video Engine 🎬

> **星游视界** — AI 驱动的视频自动生成流水线
> 从主题输入到成片输出，全自动化，成本 < $1/视频

## 概览

StarVoyage 是一套 AI 视频自动生成系统，专为 YouTube 频道「星游视界」打造：
- 输入中文主题 → 自动生成中英双语字幕完整视频
- 支持长视频（3-10 分钟）和 Shorts（60 秒内）
- 单视频生产成本 < **$1**
- 当前版本：**v0.1**（第一/二阶段 — CLI 工具）

## 系统架构

```
用户输入 → ScriptAgent → StoryboardAgent → [AssetAgent] → NarrationAgent → Composer → 成片
                    (LLM)         (LLM)          (SiliconFlow)    (Edge TTS)    (FFmpeg)
```

## 快速开始

### 前置要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行环境 |
| FFmpeg | latest | 视频合成 |
| PostgreSQL | 15+ (with pgvector) | 项目记录 + 向量存储 |
| Redis | 7+ | 任务队列 / 缓存 |

### 安装

```bash
# 1. 克隆
git clone <repo-url>
cd starvoyage-video-engine

# 2. Python 依赖
pip install -r requirements.txt

# 3. 第三方项目（不源码嵌入，只作为依赖调用）
pip install git+https://github.com/RayVentura/ShortGPT.git
pip install git+https://github.com/calesthio/OpenMontage.git

# 4. 配置数据库
psql -U postgres -c "CREATE DATABASE starvoyage;"
psql -U postgres -d starvoyage -c "CREATE EXTENSION vector;"

# 5. 配置 API 密钥
#    编辑 src/config/config.yaml，或设置环境变量：
export OPENROUTER_API_KEY="sk-or-v1-..."
export SILICONFLOW_API_KEY="sf-..."
```

### 初始化数据库

```bash
python main.py init-db
# => ✅ Database schema initialised.
```

### 使用示例

**生成完整视频：**
```bash
python main.py run \
  --topic "成都火锅的百年历史" \
  --niche china_food \
  --duration 180 \
  --format youtube
```

**只生成脚本 + 分镜（草稿模式）：**
```bash
python main.py draft \
  --topic "上海外滩的清晨" \
  --niche china_city
```

**生成 60 秒 Shorts：**
```bash
python main.py run \
  --topic "深圳华强北电子市场" \
  --niche china_tech \
  --duration 60 \
  --format shorts
```

**查看可用主题模板：**
```bash
python main.py list-niches
```

**查看历史项目：**
```bash
python main.py list-projects
```

**视频质量检查：**
```bash
python main.py check-quality output/20260622_120000_final.mp4
```

## 项目结构

```
starvoyage-video-engine/
├── src/
│   ├── config/              # 配置 (YAML + 环境变量)
│   │   ├── config.yaml      # 主配置文件（DB/Redis/API keys）
│   │   └── settings.py      # 配置加载逻辑
│   ├── db/                  # 数据库层
│   │   ├── postgres.py       # PostgreSQL + pgvector
│   │   └── redis_client.py   # Redis 连接
│   ├── models/              # AI 模型统一接口
│   │   ├── llm.py            # LLM (OpenRouter)
│   │   ├── video.py          # 视频生成 (SiliconFlow)
│   │   └── tts.py            # TTS (Edge TTS)
│   ├── pipeline/            # 流水线编排
│   │   ├── orchestrator.py   # 主编排器
│   │   ├── script_agent.py   # 脚本生成 Agent
│   │   ├── storyboard_agent.py # 分镜规划 Agent
│   │   ├── asset_agent.py    # 素材生成 Agent (Phase 3 stub)
│   │   ├── narration_agent.py # 配音 + 字幕 Agent
│   │   └── composer.py       # FFmpeg 合成
│   ├── templates/           # 内容模板
│   │   ├── niches/           # 主题配置 (YAML)
│   │   └── prompts/          # LLM Prompt 模板
│   ├── cli.py               # CLI 参数解析
│   ├── main.py              # 入口
│   └── __main__.py           # python -m src
├── requirements.txt
├── .env.example
└── README.md
```

## 数据库配置

所有数据库配置在 `src/config/config.yaml` 中统一管理（默认值）：

| 配置项 | 默认值 |
|--------|--------|
| PostgreSQL | `postgres:ABC123###@127.0.0.1:5432/starvoyage` |
| Redis | `:ABC123###@127.0.0.1:6379/0` |
| OpenRouter | 需填写 API Key |
| SiliconFlow | 需填写 API Key |

## 开发路线图

### ✅ 第一阶段：流水线跑通
- [x] Python 项目结构
- [x] LLM 脚本生成 (OpenRouter / DeepSeek)
- [x] 分镜规划 (LLM)
- [x] Edge TTS 配音
- [x] FFmpeg 合成（拼接 + 字幕）
- [x] CLI 命令行

### ✅ 第二阶段：质量提升
- [x] 主题配置文件（4 niche）
- [x] 中英双语字幕
- [x] 背景音乐自动匹配
- [x] 封面图接口 (SiliconFlow)
- [x] 视频质量检查

### 🔜 第三阶段：管理界面
- [ ] Next.js 任务管理界面
- [ ] 任务提交 / 进度 / 历史
- [ ] 脚本人工审核
- [ ] Docker Compose 部署

### 🔜 第四阶段：产品化
- [ ] 用户系统
- [ ] 多租户
- [ ] API 对外接口
- [ ] 频道风格自定义

## 开源依赖

本系统基于以下开源项目构建，仅作调用，不源码嵌入：

- **[ShortGPT](https://github.com/RayVentura/ShortGPT)** — 短视频自动化基础框架
- **[OpenMontage](https://github.com/calesthio/OpenMontage)** — Agent 视频生产框架
- **[edge-tts](https://github.com/rany2/edge-tts)** — 免费微软 Edge TTS
- **[FFmpeg](https://ffmpeg.org/)** — 视频处理核心

## 许可证

MIT
