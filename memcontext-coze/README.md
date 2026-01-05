# Coze 视频理解端插件

> 📖 本指南将帮助你在 Coze（扣子）平台上使用 MemContext 视频理解端插件，实现本地视频文件的智能分析和理解。

## 📋 目录

- [概述](#概述)
- [功能特性](#功能特性)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [工作原理](#工作原理)
- [架构说明](#架构说明)
- [配置步骤](#配置步骤)
- [API 接口说明](#api-接口说明)
- [视频处理流程](#视频处理流程)
- [使用示例](#使用示例)
- [环境变量说明](#环境变量说明)
- [文件结构](#文件结构)
- [故障排除](#故障排除)
- [常见问题 FAQ](#常见问题-faq)
- [参考文档](#参考文档)

---

## 概述

这是一个 **Coze 端插件（localplugin）**，提供本地视频理解功能。插件会在用户本地运行，通过 cozepy SDK 连接到扣子平台，实现本地视频文件的智能分析和理解。

### 核心能力

- ✅ **本地视频分析**：支持分析本地视频文件，提取视频内容描述
- ✅ **多模态理解**：支持视频、音频、文字的多模态内容理解
- ✅ **音频转录**：可选启用音频转录功能，识别视频中的语音内容
- ✅ **OCR 识别**：可选启用文字识别，提取视频中的文字信息
- ✅ **时间线生成**：自动生成视频的时间线，包含关键时间点和描述
- ✅ **隐私保护**：所有处理在本地完成，数据不离开本地

---

## 功能特性

### 1. 视频理解能力

- **智能视频分析**：使用豆包视频理解 API 分析视频内容
- **自动切分**：自动将长视频按 1 分钟切分成多个片段进行分析
- **结构化输出**：生成视频描述、标签和时间线信息

### 2. 多模态支持

- **视频分析**：提取视频帧内容，生成详细描述
- **音频转录**：可选启用，识别视频中的语音内容（需要 SiliconFlow API）
- **文字识别**：可选启用，识别视频中的文字内容

### 3. 任务管理

- **异步处理**：视频处理在后台异步执行，不阻塞主程序
- **状态查询**：实时查询任务处理状态和进度
- **结果缓存**：相同视频路径的处理结果会被缓存，避免重复处理

### 4. 进度追踪

- **实时进度**：提供 0-100% 的实时处理进度
- **状态更新**：支持 queued、running、succeeded、failed 四种状态
- **错误处理**：详细的错误信息和异常处理

---

## 前置要求

### 必需软件

- **Python 3.9+**
  ```bash
  python --version
  ```

- **ffmpeg**（用于视频处理）
  ```bash
  ffmpeg -version
  ```
  如果未安装，请访问 [ffmpeg 官网](https://ffmpeg.org/download.html) 下载安装

### 必需账号和密钥

#### 1. Coze 平台账号
- 注册并登录 [扣子平台](https://www.coze.cn)
- 获取个人访问令牌（PAT）

#### 2. 豆包 API Key（用于视频理解）
- 访问 [火山引擎控制台](https://console.volcengine.com/)
- 创建 API Key
- 获取模型端点信息

#### 3. SiliconFlow API Key（可选，用于音频转录）
- 访问 [SiliconFlow](https://siliconflow.cn/)
- 注册并获取 API Key

---

## 快速开始

### 5 分钟快速体验

```bash
# 1. 进入 runtime 目录
cd memcontext-coze/runtime

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（创建 .env 文件或设置系统环境变量）
export COZE_API_TOKEN="your_coze_token"
export COZE_BOT_ID="your_bot_id"
export LLM_API_KEY="your_doubao_api_key"
export LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export LLM_MODEL="doubao-seed-1-6-flash-250828"

# 4. 运行程序
python app.py --region cn

# 5. 在控制台输入问题
# 例如：C:\Users\username\Desktop\video.mp4 这个视频的内容是什么？
```

**详细步骤请参考**：[完整使用指南](COZE_USAGE_GUIDE.md)

---

## 工作原理

端插件的工作方式是：

1. **本地程序通过 SDK 连接扣子平台**（而不是扣子平台调用本地接口）
2. 当 Bot 需要调用端插件时，会触发 `CONVERSATION_CHAT_REQUIRES_ACTION` 事件
3. 本地程序处理事件，执行视频理解逻辑
4. 通过 `submit_tool_outputs` 将结果返回给 Bot

### 工作流程图

```
┌─────────────────────────────────────────────────────────┐
│  用户提问（在 Coze 平台）                                │
│  "这个视频的内容是什么？"                                │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Coze Bot（已关联端插件）                                │
│  - 识别需要调用端插件                                    │
│  - 触发 CONVERSATION_CHAT_REQUIRES_ACTION 事件         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ 通过 cozepy SDK
                        ▼
┌─────────────────────────────────────────────────────────┐
│  本地程序（runtime/app.py）                              │
│  - 监听事件                                             │
│  - 调用 video_engine 处理视频                           │
│  - 返回结果给 Bot                                       │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  返回结果给用户                                          │
│  "这个视频展示了..."                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 架构说明

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Coze 平台                             │
│  - Bot 配置和提示词                                      │
│  - 端插件管理                                            │
│  - 对话流管理                                            │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ SSE 事件流
                        │ (cozepy SDK)
                        ▼
┌─────────────────────────────────────────────────────────┐
│              本地程序 (app.py)                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Coze SDK 连接层                                 │  │
│  │  - 监听事件                                      │  │
│  │  - 处理工具调用                                  │  │
│  │  - 提交结果                                      │  │
│  └───────────────┬──────────────────────────────────┘  │
│                  │                                       │
│                  ▼                                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  视频理解引擎 (video_engine.py)                  │  │
│  │  - 任务管理                                      │  │
│  │  - 进度追踪                                      │  │
│  │  - 结果存储                                      │  │
│  └───────────────┬──────────────────────────────────┘  │
│                  │                                       │
│                  ▼                                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  VideoConverter                                  │  │
│  │  - 视频切分                                      │  │
│  │  - API 调用                                      │  │
│  │  - 结果处理                                      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
                        │ 调用
                        ▼
┌─────────────────────────────────────────────────────────┐
│              外部服务                                    │
│  - 豆包视频理解 API                                      │
│  - SiliconFlow 音频转录 API（可选）                      │
└─────────────────────────────────────────────────────────┘
```

---

## 配置步骤

### 1. 创建端插件

1. 登录 [扣子平台](https://www.coze.cn)
2. 进入 **插件管理** → **端插件**
3. 点击 **创建端插件**
4. 上传 `manifest.json` 文件（或打包整个插件目录为 ZIP）

**打包 ZIP 文件：**
```bash
cd memcontext-coze
zip -r video_local_plugin.zip manifest.json openapi.yaml
```

### 2. 关联端插件到 Bot

1. 进入你的 Bot 配置页面
2. 找到 **插件** 或 **端插件** 部分
3. 添加刚才创建的端插件

### 3. 配置 Bot 提示词

在 Bot 的提示词中加入使用端插件的说明，例如：

```
你是一个视频理解助手，可以帮助用户分析本地视频文件。

当用户询问本地视频文件的内容时，请按照以下步骤操作：

1. 使用 video_submit 工具提交视频路径
   - 参数：path（视频文件的完整路径）
   - 参数：options.need_asr（是否需要语音识别，true/false）
   - 参数：options.need_ocr（是否需要文字识别，true/false）
   - 返回：job_id（任务ID）

2. 使用 video_status 工具查询处理状态
   - 参数：job_id（从步骤1获取）
   - 持续查询直到状态为 "succeeded"

3. 使用 video_result 工具获取理解结果
   - 参数：job_id（从步骤1获取）
   - 返回：视频的描述、标签和时间线信息

请用友好的语言向用户解释视频内容。
```

### 4. 发布 Bot 到 API 渠道

**⚠️ 重要：必须发布到 API 渠道，否则无法使用端插件！**

1. 进入 Bot 的 **发布** 页面
2. 选择 **API** 渠道（不是其他渠道）
3. 点击发布
4. **记录 Bot ID**（后续配置需要）

### 5. 获取访问令牌

1. 访问 [扣子个人访问令牌](https://www.coze.cn/open/oauth/pats)
2. 点击 **创建令牌**
3. 填写令牌名称（例如：video_plugin_token）
4. 选择权限范围（至少需要 Bot 相关权限）
5. 点击 **创建**
6. **复制并保存 Token**（只显示一次）

### 6. 配置环境变量

在项目根目录创建 `.env` 文件（如果不存在）：

```env
# Coze 平台配置（必需）
COZE_API_TOKEN=your_coze_pat_token_here
COZE_BOT_ID=your_bot_id_here

# 视频理解配置（必需）
LLM_API_KEY=your_doubao_api_key_here
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-1-6-flash-250828

# 音频转录配置（可选）
ENABLE_AUDIO_TRANSCRIPTION=false
SILICONFLOW_API_KEY=your_siliconflow_api_key_here
```

### 7. 安装依赖

```bash
cd memcontext-coze/runtime

# 安装依赖
pip install -r requirements.txt
```

**如果安装失败**，可以尝试：
```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或升级 pip
pip install --upgrade pip
pip install -r requirements.txt
```

### 8. 启动程序

#### 方式1：使用 .env 文件启动（推荐）

**步骤1**：在项目根目录创建 `.env` 文件（如果还没有）

**步骤2**：启动程序

```bash
cd memcontext-coze/runtime

# 中国区
python app.py --region cn

# 国际区
python app.py --region global
```

程序会自动从 `.env` 文件读取环境变量。

#### 方式2：使用系统环境变量启动

**Windows (PowerShell)**：
```powershell
$env:COZE_API_TOKEN="your_token"
$env:COZE_BOT_ID="your_bot_id"
$env:LLM_API_KEY="your_doubao_api_key"
$env:LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
$env:LLM_MODEL="doubao-seed-1-6-flash-250828"
cd memcontext-coze\runtime
python app.py --region cn
```

**Windows (CMD)**：
```cmd
set COZE_API_TOKEN=your_token
set COZE_BOT_ID=your_bot_id
set LLM_API_KEY=your_doubao_api_key
set LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
set LLM_MODEL=doubao-seed-1-6-flash-250828
cd memcontext-coze\runtime
python app.py --region cn
```

**Linux/Mac**：
```bash
export COZE_API_TOKEN="your_token"
export COZE_BOT_ID="your_bot_id"
export LLM_API_KEY="your_doubao_api_key"
export LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export LLM_MODEL="doubao-seed-1-6-flash-250828"
cd memcontext-coze/runtime
python app.py --region cn
```

#### 方式3：使用虚拟环境启动（推荐用于生产环境）

**创建虚拟环境**：

**Windows**：
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac**：
```bash
python -m venv venv
source venv/bin/activate
```

**安装依赖并启动**：
```bash
cd memcontext-coze/runtime
pip install -r requirements.txt
python app.py --region cn
```

#### 方式4：后台运行（Linux/Mac）

**使用 nohup**：
```bash
cd memcontext-coze/runtime
nohup python app.py --region cn > app.log 2>&1 &
```

**使用 screen**：
```bash
# 安装 screen（如果没有）
# Ubuntu/Debian: sudo apt-get install screen
# CentOS/RHEL: sudo yum install screen

# 启动 screen 会话
screen -S coze_plugin

# 在 screen 中运行程序
cd memcontext-coze/runtime
python app.py --region cn

# 按 Ctrl+A 然后按 D 退出 screen（程序继续运行）
# 重新连接：screen -r coze_plugin
```

**使用 systemd（Linux 系统服务）**：

创建服务文件 `/etc/systemd/system/coze-plugin.service`：
```ini
[Unit]
Description=Coze Video Understanding Plugin
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/memcontext-coze/runtime
Environment="COZE_API_TOKEN=your_token"
Environment="COZE_BOT_ID=your_bot_id"
Environment="LLM_API_KEY=your_doubao_api_key"
Environment="LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3"
Environment="LLM_MODEL=doubao-seed-1-6-flash-250828"
ExecStart=/usr/bin/python3 /path/to/memcontext-coze/runtime/app.py --region cn
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable coze-plugin
sudo systemctl start coze-plugin
sudo systemctl status coze-plugin
```

#### 启动参数说明

```bash
python app.py [--region {cn|global}]
```

- `--region cn`：使用中国区扣子平台（默认）
- `--region global`：使用国际区扣子平台

### 9. 验证启动是否成功

**成功启动的标志**：

```
区域: cn
Base URL: https://api.coze.cn
Bot ID: your_bot_id

视频理解端插件已启动
输入 'exit' 或 'quit' 退出

-----
请输入你的问题：
```

**如果看到以上输出**，说明程序启动成功！

**如果看到错误信息**：

1. **`Error: COZE_API_TOKEN environment variable is required`**
   - 解决：检查环境变量是否设置，或 `.env` 文件是否存在

2. **`Error: COZE_BOT_ID environment variable is required`**
   - 解决：检查 `COZE_BOT_ID` 是否设置

3. **`Error: cozepy not installed`**
   - 解决：运行 `pip install -r requirements.txt`

4. **`ModuleNotFoundError: No module named 'xxx'`**
   - 解决：安装缺失的依赖包

### 10. 测试启动

启动成功后，可以输入测试问题：

```
C:\Users\username\Desktop\test.mp4 这个视频的内容是什么？
```

如果 Bot 开始调用端插件，说明一切正常！

### 11. 停止程序

**正常停止**：
- 在控制台输入 `exit` 或 `quit`
- 或按 `Ctrl+C`（Windows/Linux/Mac）

**强制停止**：
- 关闭终端窗口
- 或使用任务管理器/进程管理器结束进程

**停止后台运行的程序**：
```bash
# 查找进程
ps aux | grep "app.py"

# 停止进程（替换 PID 为实际进程ID）
kill PID

# 或强制停止
kill -9 PID
```

### 8. 使用

程序运行后，在控制台输入问题，例如：
```
C:\Users\username\Desktop\video.mp4 这个视频的内容是什么？
```

Bot 会自动调用端插件来分析视频。

---

## API 接口说明

插件提供三个 API 接口：

### 1. video_submit - 提交视频进行理解

**功能**：提交本地视频路径进行理解分析

**请求参数**：
```json
{
  "path": "C:\\Users\\username\\Desktop\\video.mp4",
  "options": {
    "need_asr": true,    // 可选，是否需要语音识别，默认 false
    "need_ocr": true     // 可选，是否需要文字识别，默认 false
  }
}
```

**返回结果**：
```json
{
  "job_id": "ac916a68-c17e-4464-9908-c688a57fb4a7"
}
```

**错误处理**：
- 如果视频路径不存在，返回错误信息
- 如果视频格式不支持，返回错误信息

### 2. video_status - 查询任务状态

**功能**：根据 job_id 查询视频理解任务的状态和进度

**请求参数**：
```json
{
  "job_id": "ac916a68-c17e-4464-9908-c688a57fb4a7"
}
```

**返回结果**：
```json
{
  "status": "running",    // queued | running | succeeded | failed
  "progress": 0.32        // 0.0 - 1.0
}
```

**状态说明**：
- `queued`：任务已创建，等待处理
- `running`：任务正在处理中
- `succeeded`：任务处理成功
- `failed`：任务处理失败

### 3. video_result - 获取理解结果

**功能**：根据 job_id 获取视频理解的结构化结果

**请求参数**：
```json
{
  "job_id": "ac916a68-c17e-4464-9908-c688a57fb4a7"
}
```

**返回结果**：
```json
{
  "caption": "视频描述内容...",
  "tags": ["短视频", "有音频", "video_api_converter"],
  "timeline": [
    {
      "start_sec": 0.0,
      "end_sec": 60.0,
      "summary": "片段摘要..."
    }
  ],
  "metadata": {
    "converter_provider": "video_api_converter",
    "video_duration": 60.0,
    "segments_count": 1
  }
}
```

**错误处理**：
- 如果任务不存在，返回错误信息
- 如果任务未完成，返回错误信息

---

## 视频处理流程

### 完整处理流程

```
用户提交视频
    ↓
1. video_submit
   - 验证视频路径
   - 创建任务（job_id）
   - 启动后台处理线程
   - 返回 job_id
    ↓
2. 后台处理（异步）
   ├─ 获取视频信息 (5%)
   ├─ 按1分钟切分视频 (10-20%)
   ├─ 提取音频并转录（可选）(15-18%)
   ├─ 分析每个视频片段 (20-90%)
   │   ├─ 编码视频为 base64 (25%)
   │   ├─ 调用豆包 API 分析 (30%)
   │   └─ 处理结果 (90%)
   └─ 生成最终结果 (100%)
    ↓
3. video_status（轮询查询）
   - 查询任务状态
   - 获取处理进度
   - 等待状态变为 succeeded
    ↓
4. video_result
   - 获取结构化结果
   - 返回给用户
```

### 进度说明

- **0.05**：获取视频信息
- **0.1-0.2**：按1分钟切分视频
- **0.15-0.18**：提取音频并转录（如果启用）
- **0.2-0.9**：分析每个视频片段
  - **0.25**：编码视频为 base64
  - **0.3**：调用豆包 API 分析（可能在这里卡住）
  - **0.9**：处理结果
- **1.0**：完成

### 处理时间估算

- **1 分钟视频**：约 30 秒 - 2 分钟
- **10 分钟视频**：约 5 - 15 分钟
- **1 小时视频**：约 30 - 60 分钟

**注意**：处理时间取决于视频长度、复杂度、网络状况和 API 响应速度。

---

## 使用示例

### 示例1：分析视频内容

**用户提问**：
```
C:\Users\username\Desktop\meeting.mp4 这个视频讲了什么？
```

**Bot 处理流程**：
1. 调用 `video_submit` 提交视频路径
2. 调用 `video_status` 查询状态（可能多次）
3. 调用 `video_result` 获取结果
4. 返回视频描述、标签和时间线

**返回结果示例**：
```json
{
  "caption": "这是一个团队会议视频，讨论了项目进度和下一步计划。",
  "tags": ["会议", "团队", "项目", "讨论"],
  "timeline": [
    {
      "start_sec": 0,
      "end_sec": 120,
      "summary": "开场和项目背景介绍"
    }
  ]
}
```

### 示例2：启用音频和文字识别

**用户提问**：
```
C:\Users\username\Desktop\tutorial.mp4 这个视频的内容是什么？需要识别语音和文字
```

**Bot 会自动设置**：
```json
{
  "path": "C:\\Users\\username\\Desktop\\tutorial.mp4",
  "options": {
    "need_asr": true,   // 启用语音识别
    "need_ocr": true    // 启用文字识别
  }
}
```

### 示例3：查询视频中的特定内容

**用户提问**：
```
C:\Users\username\Desktop\presentation.mp4 视频中提到了哪些关键步骤？
```

Bot 会分析视频并提取关键步骤信息。

---

## 环境变量说明

### 必需的环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `COZE_API_TOKEN` | 扣子平台个人访问令牌 | `pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `COZE_BOT_ID` | Bot ID（发布到 API 渠道后获取） | `1234567890123456789` |
| `LLM_API_KEY` | 豆包 API Key | `your_doubao_api_key` |
| `LLM_BASE_URL` | 豆包 API 地址 | `https://ark.cn-beijing.volces.com/api/v3` |
| `LLM_MODEL` | 豆包模型名称 | `doubao-seed-1-6-flash-250828` |

### 可选环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ENABLE_AUDIO_TRANSCRIPTION` | 是否启用音频转录 | `false` |
| `SILICONFLOW_API_KEY` | SiliconFlow API Key（启用音频转录时需要） | - |
| `SILICONFLOW_API_URL` | SiliconFlow API 地址 | `https://api.siliconflow.cn/v1/audio/transcriptions` |
| `SILICONFLOW_MODEL` | SiliconFlow 模型名称 | `TeleAI/TeleSpeechASR` |

### 环境变量优先级

程序会按以下顺序查找环境变量：

1. 系统环境变量
2. `runtime/.env` 文件
3. `memcontext-coze/.env` 文件
4. 项目根目录 `.env` 文件

**建议**：在项目根目录创建 `.env` 文件，统一管理所有配置。

---

## 文件结构

```
memcontext-coze/
├── manifest.json              # 插件清单（需要上传到扣子平台）
├── openapi.yaml               # OpenAPI 规范（包含在 manifest.json 中引用）
├── README.md                  # 本文档
├── COZE_USAGE_GUIDE.md        # 详细使用指南
├── plugin_icon/               # 插件图标目录（可选）
│   └── default_icon.png
└── runtime/                   # 本地运行程序
    ├── app.py                 # 主程序（通过 cozepy SDK 连接扣子平台）
    ├── video_engine.py        # 视频理解引擎
    ├── requirements.txt        # Python 依赖
    └── job_store/             # 任务存储目录（自动创建）
        └── jobs.json          # 任务数据文件
```

---

## 故障排除

### Bot 没有调用端插件

**问题**：Bot 直接回复无法访问本地文件，没有调用端插件

**解决方案**：
1. ✅ 确认端插件已在扣子平台创建
2. ✅ 确认端插件已关联到 Bot
3. ✅ 检查 Bot 的提示词是否包含使用端插件的说明
4. ✅ 确认本地程序正在运行

### 4015 错误：Bot 未发布到 API 渠道

**问题**：`code: 4015, msg: The bot_id has not been published to the channel Agent As API`

**解决方案**：
1. 进入 Bot 的发布页面
2. 选择 **API** 渠道（不是其他渠道）
3. 点击发布
4. 重新获取 Bot ID

### 视频理解失败

**问题**：视频处理失败或超时

**解决方案**：
1. ✅ 检查视频文件路径是否正确（使用绝对路径）
2. ✅ 确认视频文件格式支持（.mp4, .mov, .mkv, .avi, .webm, .flv）
3. ✅ 检查 `LLM_API_KEY` 等环境变量是否正确设置
4. ✅ 查看 `runtime/job_store/jobs.json` 中的错误信息
5. ✅ 确认 ffmpeg 已正确安装

### 进度卡在 0.32 不动

**问题**：视频处理进度一直停留在 0.32（32%）

**原因分析**：
- 进度 0.32 对应 VideoConverter 的 0.3（30%），卡在调用豆包 API 分析视频的步骤
- 可能是 API 调用没有超时设置，长时间等待
- 可能是视频文件较大，base64 编码后传输耗时
- 可能是网络问题或 API 服务器响应慢

**解决方案**：
1. ✅ **等待更长时间**：视频处理可能需要几分钟到几十分钟，请耐心等待
2. ✅ **检查网络连接**：确保网络连接正常，可以访问豆包 API
3. ✅ **检查 API 配置**：确认 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 配置正确
4. ✅ **查看详细日志**：查看控制台是否有 `[Job {job_id}]` 开头的日志
5. ✅ **检查任务状态**：查看 `runtime/job_store/jobs.json` 中的任务状态和错误信息
6. ✅ **尝试较小的视频**：如果视频很大，可以先用较小的视频测试

**手动查询任务状态**：
```python
from memcontext_coze.runtime.video_engine import VideoEngine

engine = VideoEngine()
job_id = "your_job_id"
status = engine.get_status(job_id)
print(f"状态: {status['status']}, 进度: {status['progress']}")
```

### 连接失败

**问题**：`[ERROR] 连接扣子平台失败`

**解决方案**：
1. ✅ 检查 `COZE_API_TOKEN` 是否正确
2. ✅ 检查 `COZE_BOT_ID` 是否正确（必须是发布到 API 渠道的 Bot ID）
3. ✅ 检查网络连接
4. ✅ 确认使用的是正确的区域（`--region cn` 或 `--region global`）

### 音频转录失败

**问题**：音频转录功能不工作

**解决方案**：
1. ✅ 检查 `ENABLE_AUDIO_TRANSCRIPTION` 是否设置为 `true`
2. ✅ 检查 `SILICONFLOW_API_KEY` 是否正确配置
3. ✅ 确认视频包含音频流
4. ✅ 检查 SiliconFlow 服务状态

---

## 常见问题 FAQ

### Q1: 端插件和普通插件有什么区别？

**A**: 
- **普通插件**：运行在云端，扣子平台主动调用插件的 API
- **端插件**：运行在本地，本地程序通过 SDK 主动连接到扣子平台

### Q2: 为什么必须发布到 API 渠道？

**A**: 端插件需要通过 API 渠道的 Bot ID 来建立连接，其他渠道（如网页、小程序）不支持端插件。

### Q3: 可以同时运行多个端插件吗？

**A**: 可以，但需要确保每个插件使用不同的端口号。

### Q4: 视频处理需要多长时间？

**A**: 取决于视频长度和复杂度，通常：
- 1 分钟视频：约 30 秒 - 2 分钟
- 10 分钟视频：约 5 - 15 分钟
- 1 小时视频：约 30 - 60 分钟

### Q5: 支持哪些视频格式？

**A**: 支持常见视频格式：`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.flv`

### Q6: 数据会上传到云端吗？

**A**: 不会。端插件在本地运行，视频文件和处理结果都保留在本地，不会上传到扣子平台。只有调用豆包 API 时，视频会被编码为 base64 发送到豆包服务器进行分析。

### Q7: 如何查看处理进度？

**A**: 可以通过 `video_status` 接口查询任务状态和进度，或者查看 `runtime/job_store/jobs.json` 文件。

### Q8: 任务可以取消吗？

**A**: 目前不支持取消正在运行的任务。如果需要，可以停止本地程序，任务状态会保留在 `jobs.json` 中。

### Q9: 相同视频会重复处理吗？

**A**: 不会。如果相同路径的视频已经成功处理过，会直接返回之前的结果，不会重复处理。

### Q10: 如何查看详细的错误信息？

**A**: 
1. 查看控制台输出
2. 查看 `runtime/job_store/jobs.json` 中的 `error` 字段
3. 查看任务状态中的错误信息

---

## 参考文档

### 官方文档

- [扣子中如何使用端插件，让智能体与本地设备交互?](https://bytedance.larkoffice.com/docx/AAAedsXYAolDEVx47yJcsth2nrd)
- [扣子官方示例](https://github.com/coze-ai/coze-cookbook/tree/main/examples/local_plugin)
- [扣子个人访问令牌](https://www.coze.cn/open/oauth/pats)

### 相关资源

- [Coze Python SDK (cozepy)](https://github.com/coze-ai/cozepy)
- [火山引擎豆包 API 文档](https://www.volcengine.com/docs/82379)
- [SiliconFlow API 文档](https://siliconflow.cn/docs)

### 项目文档

- [详细使用指南](COZE_USAGE_GUIDE.md) - 更详细的部署和使用说明
- [主项目 README](../README.md) - ContextBase 项目总览

---

**祝使用愉快！** 🎉
