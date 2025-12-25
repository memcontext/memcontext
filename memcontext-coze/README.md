# Coze 视频理解端插件

## 概述

这是一个 Coze 端插件（localplugin），提供本地视频理解功能。插件会在用户本地运行，通过 cozepy SDK 连接到扣子平台。

## 工作原理

端插件的工作方式是：
1. **本地程序通过 SDK 连接扣子平台**（而不是扣子平台调用本地接口）
2. 当 Bot 需要调用端插件时，会触发 `CONVERSATION_CHAT_REQUIRES_ACTION` 事件
3. 本地程序处理事件，执行视频理解逻辑
4. 通过 `submit_tool_outputs` 将结果返回给 Bot

## 配置步骤

### 1. 创建端插件

1. 登录 [扣子平台](https://www.coze.cn)
2. 进入 **插件管理** → **端插件**
3. 点击 **创建端插件**
4. 上传 `manifest.json` 文件（或打包整个插件目录为 ZIP）

**打包 ZIP 文件：**
```bash
cd memcontext-coze
zip -r video_local_plugin.zip manifest.json openapi.yaml plugin_icon/
```

### 2. 关联端插件到 Bot

1. 进入你的 Bot 配置页面
2. 找到 **插件** 或 **端插件** 部分
3. 添加刚才创建的端插件

### 3. 配置 Bot 提示词

在 Bot 的提示词中加入使用端插件的说明，例如：

```
当用户询问本地视频文件的内容时，使用视频理解端插件（video_local_plugin）来分析视频。
调用顺序：
1. 使用 video_submit 提交视频路径
2. 使用 video_status 查询处理状态，直到状态为 succeeded
3. 使用 video_result 获取理解结果
```

### 4. 发布 Bot 到 API 渠道

1. 进入 Bot 的 **发布** 页面
2. 选择 **API** 渠道
3. 点击发布
4. 记录 Bot ID

### 5. 获取访问令牌

1. 访问 [扣子个人访问令牌](https://www.coze.cn/open/oauth/pats)
2. 创建新的访问令牌
3. 记录 Token

### 6. 运行本地程序

```bash
cd runtime

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export COZE_API_TOKEN="your_token"
export COZE_BOT_ID="your_bot_id"
export LLM_API_KEY="your_doubao_api_key"  # 用于视频理解
export LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export LLM_MODEL="doubao-seed-1-6-flash-250828"

# 可选：如果需要音频转录
export ENABLE_AUDIO_TRANSCRIPTION="true"
export SILICONFLOW_API_KEY="your_siliconflow_api_key"

# 运行程序
python app.py --region cn
```

### 7. 使用

程序运行后，在控制台输入问题，例如：
```
/Users/a0000/Downloads/video.mp4 这个视频的内容是什么？
```

Bot 会自动调用端插件来分析视频。

## 环境变量说明

### 必需的环境变量

- `COZE_API_TOKEN`: 扣子平台访问令牌
- `COZE_BOT_ID`: Bot ID（发布到 API 渠道后获取）

### 视频理解相关的环境变量

- `LLM_API_KEY`: 豆包 API Key（用于视频理解）
- `LLM_BASE_URL`: API 地址（默认：`https://ark.cn-beijing.volces.com/api/v3`）
- `LLM_MODEL`: 模型名称（默认：`doubao-seed-1-6-flash-250828`）

### 可选环境变量

- `ENABLE_AUDIO_TRANSCRIPTION`: 是否启用音频转录（`true`/`false`）
- `SILICONFLOW_API_KEY`: SiliconFlow API Key（用于音频转录）
- `SILICONFLOW_API_URL`: SiliconFlow API 地址
- `SILICONFLOW_MODEL`: SiliconFlow 模型名称

## 文件结构

```
memcontext-coze/
├── manifest.json          # 插件清单（需要上传到扣子平台）
├── openapi.yaml           # OpenAPI 规范（包含在 manifest.json 中引用）
├── plugin_icon/           # 插件图标目录
│   └── default_icon.png
├── runtime/               # 本地运行程序
│   ├── app.py            # 主程序（通过 cozepy SDK 连接扣子平台）
│   ├── video_engine.py   # 视频理解引擎
│   ├── job_store/        # 任务存储目录（自动创建）
│   └── requirements.txt  # Python 依赖
└── README.md             # 本文档
```

## 故障排除

### Bot 没有调用端插件

**问题**：Bot 直接回复无法访问本地文件，没有调用端插件

**解决方案**：
1. 确认端插件已在扣子平台创建
2. 确认端插件已关联到 Bot
3. 检查 Bot 的提示词是否包含使用端插件的说明
4. 确认本地程序正在运行

### 4015 错误：Bot 未发布到 API 渠道

**问题**：`code: 4015, msg: The bot_id has not been published to the channel Agent As API`

**解决方案**：
1. 进入 Bot 的发布页面
2. 选择 **API** 渠道（不是其他渠道）
3. 点击发布

### 视频理解失败

**问题**：视频处理失败或超时

**解决方案**：
1. 检查视频文件路径是否正确
2. 确认视频文件格式支持（.mp4, .mov, .mkv, .avi, .webm, .flv）
3. 检查 `LLM_API_KEY` 等环境变量是否正确设置
4. 查看 `runtime/job_store/jobs.json` 中的错误信息

## 参考文档

- [扣子中如何使用端插件，让智能体与本地设备交互?](https://bytedance.larkoffice.com/docx/AAAedsXYAolDEVx47yJcsth2nrd)
- [扣子官方示例](https://github.com/coze-ai/coze-cookbook/tree/main/examples/local_plugin)
- [扣子个人访问令牌](https://www.coze.cn/open/oauth/pats)
