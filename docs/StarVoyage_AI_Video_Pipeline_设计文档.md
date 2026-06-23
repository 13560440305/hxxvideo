# 星游视界 AI 视频自动生成系统设计文档

> **项目代号**：StarVoyage Video Engine  
> **版本**：v0.1 初稿  
> **日期**：2026-06-22  
> **作者**：星游视界技术团队

---

## 1. 项目背景与目标

### 1.1 背景

星游视界（StarVoyage）是一个面向全球受众的 YouTube 频道，专注展示中国城市、美食、科技与制造业内容。当前内容生产依赖人工拍摄和剪辑，产能受限，难以高频输出。

为提升内容生产效率，计划构建一套 **AI 驱动的视频自动生成流水线**，实现从主题输入到成片输出的全自动化，大幅降低单视频制作时间和成本。

### 1.2 目标

- 输入一个中文主题，自动生成带中英双语字幕的完整视频
- 单视频生产成本控制在 **$1 以内**
- 支持 YouTube 长视频（3-10 分钟）和 Shorts（60 秒内）两种格式
- 初期服务星游视界频道内部使用，后期可独立产品化

### 1.3 非目标（初期不做）

- 实时直播视频生成
- 用户多租户 SaaS 平台
- 视频自动上传（手动审核后再上传）

---

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户输入层                                 │
│  主题输入 → 风格选择 → 时长设定 → 语言配置                    │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  Agent 编排层（核心）                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 脚本     │  │ 分镜     │  │ 素材     │  │ 后期     │   │
│  │ Agent    │→ │ Agent    │→ │ Agent    │→ │ Agent    │   │
│  │(LLM规划) │  │(场景拆解) │  │(生成/检索)│  │(合成输出) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                   能力层（外部 API）                           │
│                                                             │
│  LLM        视频生成        TTS配音       字幕/后期           │
│  DeepSeek   SiliconFlow    Edge TTS      FFmpeg             │
│  Qwen3      通义万象        Azure TTS     Remotion           │
│             Wan2.2         ElevenLabs    Whisper            │
└─────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                   存储层                                      │
│  PostgreSQL（项目记录）  Redis（任务队列）  本地文件系统（素材） │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心流水线设计

### 3.1 完整流程（5 个阶段）

```
阶段1: 脚本生成
  输入: 主题（中文）、风格、时长
  处理: LLM 生成中文脚本 → 翻译为英文旁白
  输出: JSON 格式脚本（含场景划分、中英文本）

阶段2: 分镜规划
  输入: 脚本 JSON
  处理: LLM 为每个场景生成视觉描述 + 镜头关键词
  输出: 分镜表（场景时长、视觉 Prompt、镜头类型）

阶段3: 素材生成
  输入: 分镜表
  处理: 并行调用视频/图像生成 API
  输出: 各场景视频片段（mp4）

阶段4: 配音与字幕
  输入: 英文旁白脚本
  处理: TTS 生成配音 → Whisper 生成字幕时间轴
  输出: 音频文件（wav）+ 字幕文件（srt/ass）

阶段5: 合成输出
  输入: 视频片段 + 音频 + 字幕
  处理: FFmpeg 拼接 → 烧录字幕 → 添加背景音乐 → 输出成片
  输出: 最终 MP4 文件 + 封面图
```

### 3.2 脚本生成模块

**输入格式：**

```json
{
  "topic": "成都宽窄巷子的街头美食",
  "style": "documentary",
  "duration": 180,
  "target_audience": "global",
  "language": { "script": "zh", "narration": "en" }
}
```

**LLM Prompt 模板（脚本生成）：**

```
你是一位纪录片脚本作家，专注于向全球观众展示中国文化。
请为主题「{topic}」创作一个{duration}秒的视频脚本。

要求：
- 分为 {scene_count} 个场景，每场景约 {scene_duration} 秒
- 风格：真实、温暖、有故事感
- 每场景包含：中文解说词、英文旁白、视觉描述关键词
- 第一个场景必须有强烈的视觉钩子（Hook）
- 输出格式为 JSON

输出结构：
{
  "title": "视频标题（英文）",
  "description": "频道简介（英文，150字以内）",
  "scenes": [
    {
      "id": 1,
      "duration": 15,
      "zh_narration": "中文解说",
      "en_narration": "English narration",
      "visual_prompt": "cinematic shot of...",
      "shot_type": "wide|medium|close|aerial"
    }
  ]
}
```

### 3.3 视频素材生成模块

采用**分级策略**，根据场景重要性选择不同方案：

| 场景类型 | 素材来源 | 成本 |
|---------|---------|------|
| Hook 开场（必看）| SiliconFlow Wan2.2 视频生成 | ~$0.15/片段 |
| 主要内容场景 | SiliconFlow CogVideoX / 通义万象 | ~$0.08/片段 |
| 过渡/补充场景 | Pexels 免费素材库 | 免费 |
| 封面图 | Flux via SiliconFlow（图像生成）| ~$0.02 |

**视频生成 API 调用示例（SiliconFlow）：**

```python
import requests

def generate_video_clip(visual_prompt: str, duration: int = 5) -> str:
    response = requests.post(
        "https://api.siliconflow.cn/v1/video/submit",
        headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}"},
        json={
            "model": "Wan-AI/Wan2.2-T2V-A14B",
            "prompt": visual_prompt,
            "negative_prompt": "low quality, blurry, watermark",
            "num_frames": duration * 24,
            "resolution": "1280x720",
        }
    )
    return response.json()["requestId"]
```

### 3.4 配音模块

**主配音方案：Microsoft Edge TTS（免费）**

```python
import edge_tts

async def generate_narration(text: str, output_path: str):
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-US-AndrewNeural",  # 男声纪录片风格
        rate="-5%",   # 稍慢，适合纪录片节奏
        volume="+10%"
    )
    await communicate.save(output_path)
```

**备用配音方案：**
- ElevenLabs（质量更高，$0.30/1000字符）
- Azure 认知服务 TTS（中文配音备用）

### 3.5 字幕模块

双语字幕烧录策略：
- **英文字幕**：主要字幕，底部居中，白色加黑边
- **中文字幕**：次要字幕，英文字幕上方，黄色

```python
def burn_subtitles(video_path: str, srt_en: str, srt_zh: str, output: str):
    ffmpeg_cmd = [
        "ffmpeg", "-i", video_path,
        "-vf",
        f"subtitles={srt_en}:force_style='FontSize=18,PrimaryColour=&Hffffff',"
        f"subtitles={srt_zh}:force_style='FontSize=14,PrimaryColour=&H00ffff,MarginV=60'",
        "-c:a", "copy", output
    ]
```

---

## 4. 技术选型

### 4.1 核心技术栈

| 类别 | 选型 | 理由 |
|-----|------|------|
| 后端语言 | Python 3.12 | AI 生态最完整 |
| 任务队列 | Redis + Celery | 视频生成耗时长，异步处理 |
| 数据库 | PostgreSQL + pgvector | 存储脚本/素材向量，复用历史内容 |
| 视频处理 | FFmpeg | 最稳定，功能最全 |
| 前端（管理界面）| Next.js + Tailwind | 快速搭建任务管理界面 |
| 部署 | Docker Compose | 本地和服务器一致 |

### 4.2 AI 模型选型

**LLM（脚本/分镜规划）：**

| 模型 | 用途 | 接入方式 |
|-----|------|---------|
| `deepseek/deepseek-chat-v3-0324` | 脚本生成、分镜规划 | OpenRouter |
| `deepseek/deepseek-r1` | 复杂场景策划 | OpenRouter |
| `qwen/qwen3-235b-a22b` | 中文内容优化 | OpenRouter |

**视频生成：**

| 模型 | 场景 | 平台 |
|-----|------|------|
| Wan2.2-T2V-A14B | 主要场景视频 | SiliconFlow |
| CogVideoX-5B | 补充场景 | SiliconFlow |
| 通义万象 Video | 备用 | 阿里云 |

### 4.3 开源基础项目

基于以下开源项目二次开发，不从零造轮子：

- **OpenMontage**（`calesthio/OpenMontage`）：Agent 编排框架，12 条生产流水线
- **ShortGPT**（`RayVentura/ShortGPT`）：字幕、配音、剪辑基础能力
- **Jaaz**（`11cafe/jaaz`）：封面图/标题卡片设计（Canvas 系统）

---

## 5. 项目目录结构

```
starvoyage-video-engine/
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py        # 主流水线编排
│   ├── script_agent.py        # 脚本生成 Agent
│   ├── storyboard_agent.py    # 分镜规划 Agent
│   ├── asset_agent.py         # 素材生成 Agent
│   ├── narration_agent.py     # 配音生成 Agent
│   └── composer.py            # FFmpeg 合成
├── models/
│   ├── llm.py                 # LLM 统一接口（OpenRouter）
│   ├── video.py               # 视频生成统一接口（SiliconFlow）
│   └── tts.py                 # TTS 统一接口
├── templates/
│   ├── niches/
│   │   ├── china_food.yaml    # 中国美食主题配置
│   │   ├── china_city.yaml    # 中国城市主题配置
│   │   ├── china_tech.yaml    # 中国科技/制造主题配置
│   │   └── travel.yaml        # 旅游主题配置
│   └── prompts/
│       ├── script_zh.txt      # 中文脚本生成 Prompt
│       └── storyboard.txt     # 分镜规划 Prompt
├── assets/
│   ├── music/                 # 背景音乐库
│   ├── fonts/                 # 字幕字体
│   └── watermark/             # 频道水印
├── output/                    # 生成的视频输出目录
├── web/                       # Next.js 管理界面
├── docker-compose.yml
├── requirements.txt
└── main.py                    # CLI 入口
```

---

## 6. 主题配置文件设计

针对星游视界的内容方向，预设主题配置：

**`templates/niches/china_food.yaml`：**

```yaml
name: china_food
description: 中国街头美食与餐饮文化

script:
  tone: "warm, authentic, curious"
  structure: "hook → origin_story → process → taste → culture_context"
  forbidden_words: ["exotic", "weird", "strange"]
  preferred_words: ["flavorful", "traditional", "crafted", "generations"]

visuals:
  style: "cinematic, warm color grade, shallow depth of field"
  shot_types: ["close-up food", "hands cooking", "street atmosphere", "customer reactions"]
  color_mood: "warm orange and golden tones"
  avoid: ["dirty", "crowded chaos", "negative stereotypes"]

narration:
  voice: "en-US-AndrewNeural"
  pace: "relaxed, 130 wpm"
  energy: "warm and inviting"

music:
  mood: "light, curious, world music influenced"
  energy: "medium-low"
  genre: "acoustic, subtle percussion"

subtitle:
  en_style: "white, bottom center, FontSize=18"
  zh_style: "yellow, above EN sub, FontSize=14"
```

---

## 7. CLI 使用方式（目标形态）

```bash
# 生成一个关于成都美食的 3 分钟视频
python main.py run \
  --topic "成都火锅的百年历史" \
  --niche china_food \
  --duration 180 \
  --format youtube

# 生成 60 秒 Shorts
python main.py run \
  --topic "上海外滩的清晨" \
  --niche china_city \
  --duration 60 \
  --format shorts

# 只生成脚本（不生成视频，用于人工审核）
python main.py draft \
  --topic "深圳华强北电子市场" \
  --niche china_tech
```

---

## 8. 成本估算

### 8.1 单视频成本（3 分钟视频，约 8 个场景）

| 环节 | 用量 | 单价 | 费用 |
|-----|------|------|------|
| LLM 脚本+分镜 | ~5000 tokens | $0.27/1M | ~$0.001 |
| 视频生成（6 片段）| 6 × 5s clips | $0.08-0.15/片段 | ~$0.60 |
| 封面图生成 | 1 张 | $0.02 | $0.02 |
| TTS 配音 | ~500 字符 | 免费（Edge TTS）| $0 |
| 背景音乐 | 免费库 | — | $0 |
| **合计** | | | **~$0.62** |

### 8.2 月度成本预估

| 产量 | 月成本 |
|-----|------|
| 10 个视频/月 | ~$6 |
| 30 个视频/月 | ~$18 |
| 100 个视频/月 | ~$62 |

---

## 9. 开发里程碑

### 第一阶段：流水线跑通（已完成 ✅）

- [x] 搭建基础 Python 项目结构
- [x] 接入 DeepSeek via OpenRouter，实现脚本生成
- [x] 接入 SiliconFlow，实现单个视频片段生成
- [x] 实现 Edge TTS 配音
- [x] FFmpeg 基础合成（拼接 + 字幕）
- [x] CLI 命令行跑通完整流程

### 第二阶段：质量提升（已完成 ✅）

- [x] 加入星游视界主题配置文件（4 个 niche）
- [x] 优化中英双语字幕样式
- [x] 加入背景音乐自动匹配（根据 niche 自动匹配 assets/music/）
- [x] 封面图自动生成（SiliconFlow Flux 模型）
- [x] 输出质量评估（分辨率、帧率、音画同步检查）

### 第三阶段：管理界面（2 周）

- [ ] Next.js 任务管理界面
- [ ] 任务提交 / 进度查看 / 历史记录
- [ ] 脚本人工审核界面（生成后可编辑再生成）
- [ ] Docker Compose 一键部署

### 第四阶段：产品化准备（持续）

- [ ] 用户系统（Supabase）
- [ ] 多用户支持
- [ ] API 接口对外开放
- [ ] 频道风格自定义（迁移到独立产品）

---

## 10. 风险与应对

| 风险 | 概率 | 影响 | 应对方案 |
|-----|------|------|---------|
| 视频生成 API 国内访问不稳定 | 中 | 高 | SiliconFlow 主 + 通义万象备用，双路切换 |
| 生成视频质量不稳定 | 高 | 中 | 多生成取最优；加人工审核环节 |
| 视频场景与主题不符 | 中 | 中 | 细化 Visual Prompt 模板；加图像验证步骤 |
| API 成本超出预期 | 低 | 中 | 设置单视频成本硬上限（$2），超出报警 |
| FFmpeg 合成音画不同步 | 低 | 高 | 每段素材标准化时长；统一帧率 24fps |

---

## 11. 参考资源

- [OpenMontage](https://github.com/calesthio/OpenMontage) - Agent 视频生产框架
- [ShortGPT](https://github.com/RayVentura/ShortGPT) - 短视频自动化基础框架
- [Verticals v3](https://github.com/rushindrasinha/youtube-shorts-pipeline) - YouTube Shorts 一键流水线
- [SiliconFlow API 文档](https://docs.siliconflow.cn) - 视频生成 API
- [Edge TTS](https://github.com/rany2/edge-tts) - 免费 TTS
- [Jaaz](https://github.com/11cafe/jaaz) - 封面图/设计素材生成

---

*文档版本：v0.1 | 下次更新：完成第一阶段开发后*
