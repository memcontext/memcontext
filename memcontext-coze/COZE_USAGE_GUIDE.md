# Coze 平台使用指南 - MemContext 视频理解端插件

> 📖 本指南将帮助你在 Coze（扣子）平台上使用 MemContext 视频理解端插件，实现本地视频文件的智能分析和理解。

## 📋 目录

- [什么是端插件？](#什么是端插件)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [环境变量配置](#环境变量配置)
- [使用示例](#使用示例)
- [故障排除](#故障排除)
- [参考文档](#参考文档)

---

## 什么是端插件？

**端插件（Local Plugin）** 是 Coze 平台的一种特殊插件类型，它允许你在本地运行程序，通过 SDK 连接到扣子平台，实现本地资源（如本地文件、本地服务）的访问。

### 工作原理

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

**关键点**：
- ✅ 本地程序通过 SDK **主动连接**到扣子平台（不是被动接收请求）
- ✅ 支持访问本地文件系统（视频文件、图片等）
- ✅ 数据不离开本地，保护隐私
- ✅ 可以调用本地 AI 模型或服务

---

## 前置要求

### 1. 必需软件

- **Python 3.9+**
  ```bash
  python --version
  ```

- **Git**（用于克隆项目）
  ```bash
  git --version
  ```

### 2. 必需账号和密钥

#### Coze 平台账号
- 注册并登录 [扣子平台](https://www.coze.cn)
- 获取个人访问令牌（PAT）

#### 豆包 API Key（用于视频理解）
- 访问 [火山引擎控制台](https://console.volcengine.com/)
- 创建 API Key
- 获取模型端点信息

#### SiliconFlow API Key（可选，用于音频转录）
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

# 3. 配置环境变量（创建 .env 文件）
# 见下方"环境变量配置"章节

# 4. 运行程序
python app.py --region cn
```

---

## 详细步骤

### 第一步：在 Coze 平台创建端插件

#### 1.1 准备插件文件

**方式1：直接上传 manifest.json（推荐）**

1. 进入项目目录：
   ```bash
   cd memcontext-coze
   ```

2. 确保以下文件存在：
   - `manifest.json` - 插件清单文件
   - `openapi.yaml` - OpenAPI 规范文件

**方式2：打包为 ZIP 文件**

```bash
cd memcontext-coze
zip -r video_local_plugin.zip manifest.json openapi.yaml
```

#### 1.2 在扣子平台创建插件

1. 登录 [扣子平台](https://www.coze.cn)
2. 进入 **插件管理** → **端插件**
3. 点击 **创建端插件** 按钮
4. 上传 `manifest.json` 文件（或上传 ZIP 文件）
5. 填写插件信息：
   - **插件名称**：视频理解端插件
   - **插件描述**：本地视频理解插件，提供视频分析、状态查询和结果获取功能
6. 点击 **创建**

**重要提示**：
- `manifest.json` 中的 `api.url` 字段指向 `http://localhost:3333/openapi.yaml`
- 这个 URL 是给扣子平台看的，实际运行时本地程序会提供这个服务

### 第二步：创建或选择 Bot

#### 2.1 创建新 Bot

1. 在扣子平台点击 **创建 Bot**
2. 填写 Bot 名称和描述
3. 点击 **创建**

#### 2.2 关联端插件到 Bot

1. 进入 Bot 的 **插件** 页面
2. 点击 **添加插件**
3. 选择刚才创建的 **视频理解端插件**
4. 点击 **确认**

### 第三步：配置 Bot 提示词

在 Bot 的 **提示词** 页面，添加以下内容：

```
你是一个视频理解助手，可以帮助用户分析本地视频文件。

当用户询问本地视频文件的内容时，请按照以下步骤操作：

1. 使用 video_submit 工具提交视频路径
   - 参数：path（视频文件的完整路径）
   - 返回：job_id（任务ID）

2. 使用 video_status 工具查询处理状态
   - 参数：job_id（从步骤1获取）
   - 持续查询直到状态为 "succeeded"

3. 使用 video_result 工具获取理解结果
   - 参数：job_id（从步骤1获取）
   - 返回：视频的描述、标签和时间线信息

请用友好的语言向用户解释视频内容。
```

### 第四步：发布 Bot 到 API 渠道

**⚠️ 重要：必须发布到 API 渠道，否则无法使用端插件！**

1. 进入 Bot 的 **发布** 页面
2. 选择 **API** 渠道（不是其他渠道）
3. 点击 **发布**
4. **记录 Bot ID**（后续配置需要）

### 第五步：获取访问令牌

1. 访问 [扣子个人访问令牌](https://www.coze.cn/open/oauth/pats)
2. 点击 **创建令牌**
3. 填写令牌名称（例如：video_plugin_token）
4. 选择权限范围（至少需要 Bot 相关权限）
5. 点击 **创建**
6. **复制并保存 Token**（只显示一次）

### 第六步：配置环境变量

在项目根目录创建 `.env` 文件（如果不存在）：

```bash
# Windows
type nul > .env

# Linux/Mac
touch .env
```

编辑 `.env` 文件，添加以下配置：

```env
# ============================================
# Coze 平台配置（必需）
# ============================================
# 扣子平台个人访问令牌
COZE_API_TOKEN=your_coze_pat_token_here

# Bot ID（发布到 API 渠道后获取）
COZE_BOT_ID=your_bot_id_here

# ============================================
# 视频理解配置（必需）
# ============================================
# 豆包 API Key（用于视频理解）
LLM_API_KEY=your_doubao_api_key_here

# 豆包 API 地址
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# 豆包模型名称
LLM_MODEL=doubao-seed-1-6-flash-250828

# ============================================
# 音频转录配置（可选）
# ============================================
# 是否启用音频转录
ENABLE_AUDIO_TRANSCRIPTION=false

# SiliconFlow API Key（用于音频转录）
SILICONFLOW_API_KEY=your_siliconflow_api_key_here

# SiliconFlow API 地址（可选，使用默认值）
# SILICONFLOW_API_URL=https://api.siliconflow.cn/v1

# SiliconFlow 模型名称（可选，使用默认值）
# SILICONFLOW_MODEL=paraformer-realtime-v2
```

**配置说明**：

| 变量名 | 是否必需 | 说明 |
|--------|---------|------|
| `COZE_API_TOKEN` | ✅ 必需 | 扣子平台个人访问令牌 |
| `COZE_BOT_ID` | ✅ 必需 | Bot ID（发布到 API 渠道后获取） |
| `LLM_API_KEY` | ✅ 必需 | 豆包 API Key |
| `LLM_BASE_URL` | ✅ 必需 | 豆包 API 地址 |
| `LLM_MODEL` | ✅ 必需 | 豆包模型名称 |
| `ENABLE_AUDIO_TRANSCRIPTION` | ⭕ 可选 | 是否启用音频转录（true/false） |
| `SILICONFLOW_API_KEY` | ⭕ 可选 | SiliconFlow API Key（启用音频转录时需要） |

### 第七步：安装依赖

```bash
cd memcontext-coze/runtime
pip install -r requirements.txt
```

**依赖包**：
- `cozepy>=0.8.0` - Coze Python SDK
- `python-dotenv` - 环境变量管理

### 第八步：运行本地程序

```bash
cd memcontext-coze/runtime

# 中国区
python app.py --region cn

# 国际区
python app.py --region com
```

**运行成功标志**：
```
[INFO] 连接到扣子平台成功
[INFO] 开始监听事件...
```

### 第九步：测试使用

#### 方式1：在 Coze 平台测试

1. 打开你的 Bot 对话页面
2. 输入问题，例如：
   ```
   D:\Videos\demo.mp4 这个视频的内容是什么？
   ```
3. Bot 会自动调用端插件分析视频
4. 等待处理完成，查看结果

#### 方式2：通过命令行测试

程序运行后，在控制台输入问题：
```
/Users/a0000/Downloads/video.mp4 这个视频的内容是什么？
```

---

## 环境变量配置

### 完整配置示例

```env
# Coze 平台
COZE_API_TOKEN=pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
COZE_BOT_ID=1234567890123456789

# 豆包 API
LLM_API_KEY=your_doubao_api_key
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-1-6-flash-250828

# 音频转录（可选）
ENABLE_AUDIO_TRANSCRIPTION=true
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 环境变量优先级

程序会按以下顺序查找环境变量：

1. 系统环境变量
2. `runtime/.env` 文件
3. `memcontext-coze/.env` 文件
4. 项目根目录 `.env` 文件

**建议**：在项目根目录创建 `.env` 文件，统一管理所有配置。

---

## 使用示例

### 示例1：分析视频内容

**用户提问**：
```
D:\Videos\meeting.mp4 这个视频讲了什么？
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
    },
    {
      "start_sec": 120,
      "end_sec": 300,
      "summary": "讨论当前项目进度和遇到的问题"
    }
  ]
}
```

### 示例2：查询视频中的特定内容

**用户提问**：
```
D:\Videos\tutorial.mp4 视频中提到了哪些关键步骤？
```

Bot 会分析视频并提取关键步骤信息。

### 示例3：视频摘要

**用户提问**：
```
D:\Videos\presentation.mp4 给我一个这个视频的摘要
```

Bot 会生成视频的详细摘要。

---

## 故障排除

### 问题1：Bot 没有调用端插件

**症状**：Bot 直接回复无法访问本地文件，没有调用端插件

**可能原因**：
1. 端插件未正确创建
2. 端插件未关联到 Bot
3. Bot 提示词未包含使用说明
4. 本地程序未运行

**解决方法**：
1. ✅ 检查端插件是否在扣子平台创建成功
2. ✅ 确认端插件已关联到 Bot（在 Bot 的插件页面查看）
3. ✅ 检查 Bot 提示词是否包含使用端插件的说明
4. ✅ 确认本地程序正在运行（`python app.py --region cn`）

### 问题2：4015 错误 - Bot 未发布到 API 渠道

**错误信息**：
```
code: 4015, msg: The bot_id has not been published to the channel Agent As API
```

**解决方法**：
1. 进入 Bot 的 **发布** 页面
2. 选择 **API** 渠道（不是其他渠道）
3. 点击 **发布**
4. 重新获取 Bot ID

### 问题3：连接失败

**错误信息**：
```
[ERROR] 连接扣子平台失败
```

**可能原因**：
1. `COZE_API_TOKEN` 错误或过期
2. `COZE_BOT_ID` 错误
3. 网络问题

**解决方法**：
1. ✅ 检查 `COZE_API_TOKEN` 是否正确
2. ✅ 检查 `COZE_BOT_ID` 是否正确（必须是发布到 API 渠道的 Bot ID）
3. ✅ 检查网络连接
4. ✅ 确认使用的是正确的区域（`--region cn` 或 `--region com`）

### 问题4：视频理解失败

**错误信息**：
```
[ERROR] 视频处理失败
```

**可能原因**：
1. 视频文件路径不正确
2. 视频格式不支持
3. `LLM_API_KEY` 配置错误
4. 视频文件损坏

**解决方法**：
1. ✅ 检查视频文件路径是否正确（使用绝对路径）
2. ✅ 确认视频格式支持（.mp4, .mov, .mkv, .avi, .webm, .flv）
3. ✅ 检查 `LLM_API_KEY` 等环境变量是否正确
4. ✅ 尝试用其他视频文件测试
5. ✅ 查看 `runtime/job_store/jobs.json` 中的错误信息

### 问题5：音频转录失败

**错误信息**：
```
[ERROR] 音频转录失败
```

**可能原因**：
1. `SILICONFLOW_API_KEY` 未配置或错误
2. `ENABLE_AUDIO_TRANSCRIPTION` 未设置为 `true`
3. SiliconFlow 服务不可用

**解决方法**：
1. ✅ 检查 `SILICONFLOW_API_KEY` 是否正确配置
2. ✅ 确认 `ENABLE_AUDIO_TRANSCRIPTION=true`
3. ✅ 检查 SiliconFlow 服务状态
4. ✅ 如果不需要音频转录，可以设置 `ENABLE_AUDIO_TRANSCRIPTION=false`

### 问题6：依赖安装失败

**错误信息**：
```
ERROR: Could not find a version that satisfies the requirement cozepy
```

**解决方法**：
1. ✅ 升级 pip：`pip install --upgrade pip`
2. ✅ 使用国内镜像：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
3. ✅ 检查 Python 版本（需要 3.9+）

### 问题7：端口被占用

**错误信息**：
```
[ERROR] 端口 3333 已被占用
```

**解决方法**：
1. ✅ 查找占用端口的进程：
   ```bash
   # Windows
   netstat -ano | findstr :3333
   
   # Linux/Mac
   lsof -i :3333
   ```
2. ✅ 结束占用端口的进程
3. ✅ 或修改 `app.py` 中的端口号（不推荐）

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

**A**: 不会。端插件在本地运行，视频文件和处理结果都保留在本地，不会上传到扣子平台。

---

## 技术支持

如果遇到问题，可以：

1. 查看 [故障排除](#故障排除) 章节
2. 查看项目 README.md
3. 提交 Issue 到项目仓库

---

**祝使用愉快！** 🎉

