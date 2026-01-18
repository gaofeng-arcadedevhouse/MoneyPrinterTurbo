# 更新日志

## 2026-01-17 TTS 模块重构

### 概述
本次更新将项目的 TTS（文字转语音）模块从多种方案（Edge TTS、Azure TTS、SiliconFlow、Gemini）统一替换为**阿里云 Qwen3-TTS-Flash**，简化了代码架构并提升了中文语音合成质量。

### 主要变更

#### 1. TTS 服务替换
- **移除**：Edge TTS、Azure TTS V1/V2、SiliconFlow TTS、Gemini TTS
- **新增**：阿里云 Qwen3-TTS-Flash 语音合成
- 支持的声音：Cherry（甜美）、Serena（知性）、Ethan（成熟）、Chelsie（活力）等
- 支持中文和英文语音

#### 2. 依赖更新 (`requirements.txt`)
- 升级 `dashscope` 至 `>=1.24.6`
- 移除 `edge-tts`
- 移除 `azure-cognitiveservices-speech`

#### 3. 代码重构

**`app/services/voice.py`**
- 从约 1771 行精简至约 400 行
- 新增 `get_aliyun_voices()` 获取阿里云声音列表
- 新增 `aliyun_tts()` 使用 Qwen3-TTS-Flash 模型
- 新增 `SimpleSubMaker` 类用于字幕时间戳管理
- 保留 `parse_voice_name()`、`get_audio_duration()`、`create_subtitle()` 等兼容函数

**`app/config/config.py`**
- 移除 `azure` 和 `siliconflow` 配置
- 新增 `aliyun` 配置项

**`config.example.toml`**
- 移除 `[azure]` 和 `[siliconflow]` 配置节
- 新增 `[aliyun]` 配置节，包含 `api_key` 和 `default_voice`

**`webui/Main.py`**
- 移除多 TTS 服务器选择下拉框
- 简化为阿里云专用配置界面
- 添加阿里云 API Key 输入框和配置说明

### 配置说明

使用前需要在阿里云 DashScope 控制台获取 API Key：
- 获取地址：https://dashscope.console.aliyun.com/apiKey
- 在配置文件 `config.toml` 或 WebUI 中设置 `aliyun_api_key`

---

## 2026-01-18 混合素材检索功能

### 概述
新增本地素材库与第三方素材库（Pexels/Pixabay）的**混合检索**功能，优先使用本地素材，减少网络请求和版权风险。

### 功能特点
1. **本地素材优先**：搜索时优先匹配本地素材库
2. **LLM 智能匹配**：使用 AI 判断素材与搜索词的相关性
3. **标签系统**：通过文件名中的标签进行语义匹配
4. **自动降级**：本地无匹配时自动搜索第三方

### 素材命名规范
```
格式：视频名称(标签1,标签2,标签3).mp4

示例：
├── 蓝天白云(sky,cloud,nature,blue).mp4
├── 城市夜景(city,night,building,light).mp4
└── 科技数据(technology,data,digital,code).mp4
```

### 配置说明

在 `config.toml` 中添加：
```toml
# 启用混合搜索
enable_hybrid_search = true

# 本地素材库目录
local_material_library = "G:/素材库/videos"
```

### 代码变更

**`app/services/material.py`**
- 新增 `parse_material_tags()` 解析文件名标签
- 新增 `scan_local_library()` 扫描本地素材库
- 新增 `match_local_material_with_llm()` LLM 智能匹配
- 新增 `search_videos_hybrid()` 混合搜索入口
- 修改 `download_videos()` 集成混合搜索

**`config.example.toml`**
- 新增 `enable_hybrid_search` 配置项
- 新增 `local_material_library` 配置项
