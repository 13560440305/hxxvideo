# StarVoyage Background Music Library

将背景音乐文件放入此目录，Pipeline 会自动匹配。

## 自动匹配规则

根据 niche 模板自动选择音乐：

| 模板 | 推荐曲风 | 示例文件名 |
|------|---------|-----------|
| `china_food` | acoustic, subtle percussion | `china_food_light.mp3` |
| `china_city` | electronic-orchestral, ambient | `china_city_uplifting.mp3` |
| `china_tech` | electronic, synthwave | `china_tech_energetic.mp3` |
| `travel` | orchestral, nature soundscape | `travel_serene.mp3` |

文件名包含 niche 名称（如 `china_food_xxx.mp3`）会自动匹配对应模板。

## 免费背景音乐推荐

- **Pixabay Music**: https://pixabay.com/music/
- **Uppbeat**: https://uppbeat.io/
- **Free Music Archive**: https://freemusicarchive.org/
- **YouTube Audio Library**: YouTube Studio → Audio Library

## 支持的格式

- `.mp3`
- `.wav`
- `.flac`
- `.ogg`

## 注意

- 音乐文件建议 30 秒以上，保证循环播放不突兀
- 默认音量 15%（可在 `--bg-music-volume` 调整）
- 不放入任何文件则跳过背景音乐
