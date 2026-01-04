# n8n 记忆管理服务 - 超详细部署指南

> 🎯 专为完全零基础小白设计的超详细教程，每个步骤都有详细说明和验证方法

## 📋 目录

### 基础部分
- [什么是这个服务？](#什么是这个服务)
- [架构说明：服务是如何运行的？](#架构说明服务是如何运行的)
- [前置要求检查清单](#前置要求检查清单)

### 部署步骤（按顺序执行）
- [第一步：下载代码](#第一步下载代码)
- [第二步：安装 Python 依赖](#第二步安装-python-依赖)
- [第三步：配置文件](#第三步配置文件)
- [第四步：启动服务](#第四步启动服务)
- [第五步：在 n8n 平台安装插件](#第五步在-n8n-平台安装插件)
- [第六步：在 n8n 中创建工作流](#第六步在-n8n-中创建工作流)

### 参考文档
- [工作流程图解](#工作流程图解)
- [完整测试流程](#完整测试流程)

### 问题排查
- [常见问题详细排查](#常见问题详细排查)

### 进阶
- [进阶使用](#进阶使用)

---

## 什么是这个服务？

这是一个**记忆管理 API 服务**，可以：

- ✅ **记住对话**：保存用户和 AI 的对话内容，下次可以回忆起来
- ✅ **智能检索**：根据问题自动查找相关记忆，生成个性化回复
- ✅ **视频处理**：上传视频，自动提取内容并建立记忆
- ✅ **多模态支持**：支持文本、视频、音频、图片等多种格式

**简单来说**：让你的 n8n 工作流拥有"记忆"功能，可以记住历史对话和内容。

**工作流程示意**：
```
用户提问 → n8n 工作流 → 记忆服务 → 查找相关记忆 → 生成个性化回复 → 返回给用户
```

---

## 架构说明：服务是如何运行的？

### 运行架构

**简单说明**：这是一个记忆管理 API 服务，运行在你的本地机器上，n8n 工作流通过 HTTP 请求调用它。

#### 1. n8ndemo/app.py 服务

**运行位置**：你的本地机器上，监听端口 5019

**功能**：
- 提供记忆管理 API 接口
- 处理记忆的添加、检索、更新
- 支持视频、音频等多媒体文件处理

**启动方式**：
```bash
cd n8ndemo
python app.py
```

#### 2. n8n 平台

**运行位置**：你的 n8n 平台（本地或云端）

**功能**：
- 创建工作流
- 通过 HTTP Request 节点调用记忆服务
- 处理业务逻辑

**假设**：你已经安装并运行了 n8n 平台

#### 3. 两者如何通信？

**通信流程**：
```
┌─────────────────────────────────────────────────────────┐
│  n8n 平台（你的 n8n 实例）                              │
│  - 可以是本地 n8n（localhost:5678）                    │
│  - 也可以是云端 n8n                                     │
│  - 通过 HTTP Request 节点发送请求                       │
│      ↓                                                  │
│  http://localhost:5019/api/memory/search              │
│  或 http://你的服务器IP:5019/api/memory/search         │
│      ↓                                                  │
└─────────────────────────────────────────────────────────┘
                    │
                    │ HTTP 请求
                    ▼
┌─────────────────────────────────────────────────────────┐
│  n8ndemo/app.py (本地运行)                             │
│  - 运行在你的机器上                                      │
│  - 端口: 5019                                           │
│  - 接收 HTTP 请求                                        │
│      ↓                                                  │
│  调用 memcontext 模块处理记忆                           │
│      ↓                                                  │
│  返回 JSON 响应                                         │
└─────────────────────────────────────────────────────────┘
```

**关键点**：
- 如果 n8n 和 app.py 在同一台机器：使用 `http://localhost:5019`
- 如果 n8n 在云端，app.py 在本地：需要配置端口转发或使用公网 IP
- 通信使用标准的 HTTP/HTTPS 协议

### 总结

**架构特点**：
- ✅ 服务运行在本地，简单直接
- ✅ 通过 HTTP API 与 n8n 通信
- ✅ 支持本地和云端 n8n 平台

---

## 前置要求检查清单

在开始之前，请逐一检查以下项目：

### ✅ 必需软件检查

#### 1. Python 3.8 或更高版本

**检查方法**：
1. 按 `Win + R` 键，输入 `cmd`，按回车打开命令行
2. 输入以下命令：
   ```bash
   python --version
   ```
3. 应该看到类似输出：
   ```
   Python 3.11.5
   ```
   **如果看到**：`'python' 不是内部或外部命令`
   **解决方法**：
   - 下载安装 Python：[https://www.python.org/downloads/](https://www.python.org/downloads/)
   - 安装时**务必勾选** "Add Python to PATH"
   - 安装完成后，重新打开命令行再试

#### 2. pip 包管理器

**检查方法**：
```bash
pip --version
```

**应该看到**：
```
pip 23.2.1 from C:\Users\...\site-packages\pip (python 3.11)
```

**如果没有安装**：Python 3.4+ 自带 pip，如果提示找不到，重新安装 Python 并勾选 "Add Python to PATH"

#### 3. n8n 平台（已安装并运行）

**假设**：你已经安装并运行了 n8n 平台

**检查方法**：
- 访问你的 n8n 地址（例如：`http://localhost:5678`）
- 如果能正常打开 n8n 界面，说明 n8n 已运行

**如果没有安装 n8n**：
- 本地安装：访问 [n8n 官网](https://n8n.io/) 查看安装说明
- 云端使用：使用 n8n Cloud 或其他 n8n 托管服务

### ✅ 必需账号和密钥

#### 1. LLM API Key（必需）

**支持的平台**：
- OpenAI（推荐）：[https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- 火山引擎：[https://console.volcengine.com/](https://console.volcengine.com/)
- 其他兼容 OpenAI API 的服务

**获取方法（以 OpenAI 为例）**：
1. 访问 [OpenAI 官网](https://platform.openai.com/)
2. 注册/登录账号
3. 进入 API Keys 页面
4. 点击 "Create new secret key"
5. 复制生成的 API Key（格式类似：`sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）
6. **重要**：API Key 只显示一次，请妥善保存

#### 2. SiliconFlow API Key（可选）

**用途**：用于视频/音频转录

**获取方法**：
1. 访问 [SiliconFlow](https://siliconflow.cn/)
2. 注册账号
3. 在控制台获取 API Key

**注意**：如果不需要视频/音频功能，可以跳过这一步

---

## 第一步：下载代码

### 1.1 获取项目代码

#### 方式1：从 GitHub 克隆（推荐）

**前提**：已安装 Git

**步骤**：
1. 打开命令行
2. 进入你想存放项目的目录，例如：
   ```bash
   cd D:\project
   ```
3. 克隆项目（替换为实际的项目地址）：
   ```bash
   git clone <项目地址>
   ```
4. 进入项目目录：
   ```bash
   cd memcontext-memcontext
   ```

#### 方式2：下载 ZIP 文件

1. 在 GitHub 页面点击 "Code" → "Download ZIP"
2. 解压 ZIP 文件到本地目录，例如：`D:\project\memcontext-memcontext`
3. 打开命令行，进入项目目录：
   ```bash
   cd D:\project\memcontext-memcontext
   ```

### 1.2 验证项目结构

**检查项目目录结构**：

在命令行中执行：
```bash
dir
```

**应该看到类似**：
```
n8ndemo/
makedemo/
difydemo/
create_video_workflow.py
README.md
.env.example
...
```

**如果没有看到这些文件**：
- 检查是否在正确的目录
- 检查项目是否完整下载

### 1.3 确认当前目录

**重要**：后续所有操作都在项目**根目录**进行（不是 n8ndemo 目录）

**验证方法**：
```bash
cd
```

**应该显示**：
```
D:\project\memcontext-memcontext
```

如果不在这个目录，执行：
```bash
cd D:\project\memcontext-memcontext
```

---

## 第二步：安装 Python 依赖

### 2.1 检查 requirements.txt

**步骤**：
1. 确认项目根目录有 `requirements.txt` 文件：
   ```bash
   dir requirements.txt
   ```

2. 或者使用 n8ndemo 目录的 `requirements.txt`（仅包含 n8ndemo 需要的依赖）：
   ```bash
   dir n8ndemo\requirements.txt
   ```

### 2.2 安装项目依赖

**方法1：使用项目根目录的 requirements.txt（推荐，包含所有依赖）**

在项目**根目录**执行：
```bash
pip install -r requirements.txt
```

**方法2：使用 n8ndemo 目录的 requirements.txt（仅 n8ndemo 依赖）**

如果你只需要运行 n8ndemo，可以使用精简版：
```bash
pip install -r n8ndemo/requirements.txt
```

**注意**：使用方式2后，还需要安装 memcontext 包（见 2.3）

**执行过程**：
- 会显示安装进度，例如：
  ```
  Collecting flask
    Downloading flask-3.0.0-py3-none-any.whl (99 kB)
  ...
  Successfully installed flask-3.0.0 ...
  ```
- 等待安装完成（可能需要几分钟）

**如果遇到错误**：
- `pip 不是内部或外部命令`：检查 Python 是否正确安装
- `Permission denied`：尝试使用 `pip install --user -r requirements.txt`
- 网络错误：检查网络连接，或使用国内镜像：
  ```bash
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

**方法3：手动安装核心依赖（如果 requirements.txt 安装失败）**

如果 `requirements.txt` 不存在或安装失败，可以手动安装所有必需的依赖包：

**步骤1：安装基础依赖**
```bash
pip install flask python-dotenv requests
```

**步骤2：安装科学计算和机器学习库**
```bash
pip install numpy sentence-transformers transformers FlagEmbedding faiss-cpu
```

**步骤3：安装 OpenAI 和其他工具库**
```bash
pip install openai typing-extensions regex
```

**完整命令（一次性安装）**：
```bash
pip install flask python-dotenv requests numpy sentence-transformers transformers FlagEmbedding faiss-cpu openai typing-extensions regex
```

**注意**：这些是运行 n8ndemo 服务所需的核心依赖。如果使用 conda 环境，建议使用 conda 安装部分包：
```bash
conda install numpy -y
pip install flask python-dotenv requests sentence-transformers transformers FlagEmbedding faiss-cpu openai typing-extensions regex
```

### 2.3 安装 memcontext 包

**步骤**：
```bash
pip install -e .
```

**执行过程**：
- 会显示安装信息
- 如果已经安装过，会显示 "Requirement already satisfied"

**验证安装**：
```bash
python -c "import memcontext; print('memcontext 安装成功')"
```

**应该看到**：
```
memcontext 安装成功
```

---

## 第三步：配置文件

### 3.1 创建 .env 文件

**重要**：`.env` 文件必须在项目**根目录**（不是 n8ndemo 目录）

#### Windows 用户创建方法

**方法1：使用命令行**
```bash
type nul > .env
```

**方法2：使用记事本**
1. 在项目根目录右键 → 新建 → 文本文档
2. 重命名为 `.env`（注意前面有个点）
3. 如果 Windows 提示"如果改变文件扩展名，文件可能不可用"，点击"是"

**方法3：使用代码编辑器**
- 使用 VS Code、Notepad++ 等编辑器创建新文件
- 保存为 `.env`（注意前面有个点）

**验证文件创建**：
```bash
dir .env
```

**应该看到**：
```
.env
```

### 3.2 编辑 .env 文件

**打开 .env 文件**（使用记事本或任何文本编辑器）

**完整配置模板**：

```env
# ============================================
# n8n API Key 配置（必需）
# ============================================
# 用于访问 n8ndemo 服务的 API Key
# 可以设置任意字符串，建议使用随机字符串
# 多个 Key 用逗号分隔
N8N_API_KEYS=my-secret-key-12345

# ============================================
# LLM 配置（必需）
# ============================================
# LLM API Key
# OpenAI 格式：sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# 火山引擎：your-volcano-engine-key
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LLM API 地址
# OpenAI: https://api.openai.com/v1
# 火山引擎: https://ark.cn-beijing.volces.com/api/v3
LLM_BASE_URL=https://api.openai.com/v1

# LLM 模型名称
# OpenAI: gpt-4, gpt-3.5-turbo, gpt-4-turbo-preview
# 火山引擎: ep-20241208200000-xxxxx
LLM_MODEL=gpt-4

# ============================================
# Embedding 模型配置（可选）
# ============================================
# 用于文本向量化
# OpenAI: text-embedding-3-small, text-embedding-3-large
# 如果不设置，会使用默认值
EMBEDDING_MODEL=text-embedding-3-small

# ============================================
# SiliconFlow 配置（可选）
# ============================================
# 用于视频/音频转录
# 如果不需要视频/音频功能，可以删除这一行
SILICONFLOW_API_KEY=your-siliconflow-api-key-here
```

### 3.3 配置说明（详细）

#### N8N_API_KEYS（必需）

**作用**：这是访问 n8ndemo 服务的密钥，用于身份验证

**设置方法**：
```env
N8N_API_KEYS=my-secret-key-12345
```

**安全提示**：
- 不要使用简单的密码（如 `123456`）
- 建议使用随机字符串，例如：`aB3xY9mK2pQ7wE5`
- 可以设置多个 Key，用逗号分隔：
  ```env
  N8N_API_KEYS=key1,key2,key3
  ```

#### LLM_API_KEY（必需）

**作用**：用于调用 LLM 服务的 API Key

**OpenAI 配置示例**：
```env
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

**火山引擎配置示例**：
```env
LLM_API_KEY=your-volcano-engine-key
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=ep-20241208200000-xxxxx
```

**获取方法**：
- OpenAI：登录 [OpenAI Platform](https://platform.openai.com/api-keys)，创建新的 API Key
- 火山引擎：登录 [火山引擎控制台](https://console.volcengine.com/)，获取 API Key

#### SILICONFLOW_API_KEY（可选）

**作用**：用于视频/音频转录

**如果不需要视频/音频功能**：
- 可以删除这一行
- 或者留空：`SILICONFLOW_API_KEY=`

**如果需要**：
1. 访问 [SiliconFlow](https://siliconflow.cn/)
2. 注册并登录
3. 在控制台获取 API Key
4. 填入配置

### 3.4 验证配置文件

**检查配置是否正确**：

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('N8N_API_KEYS:', os.getenv('N8N_API_KEYS')[:10] if os.getenv('N8N_API_KEYS') else '未设置'); print('LLM_API_KEY:', os.getenv('LLM_API_KEY')[:10] if os.getenv('LLM_API_KEY') else '未设置')"
```

**应该看到**：
```
N8N_API_KEYS: my-secret-k
LLM_API_KEY: sk-xxxxxxx
```

**如果显示"未设置"**：
- 检查 `.env` 文件是否在项目根目录
- 检查 `.env` 文件格式是否正确（没有多余的空格或引号）
- 检查变量名是否正确（大小写敏感）

---

## 第四步：启动服务

### 4.1 进入 n8ndemo 目录

**步骤**：
```bash
cd n8ndemo
```

**验证**：
```bash
cd
```

**应该显示**：
```
D:\project\memcontext-memcontext\n8ndemo
```

### 4.2 启动服务

**启动命令**：
```bash
cd n8ndemo
python app.py
```

**执行过程**：

**第一次启动**，会看到类似输出：
```
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5019
 * Running on http://192.168.1.100:5019
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 123-456-789
```

**重要提示**：
- ✅ 看到 "Running on http://127.0.0.1:5019" 说明启动成功
- ⚠️ 这个窗口**不能关闭**，关闭后服务会停止
- 🔄 如果需要停止服务，按 `Ctrl + C`

### 4.3 验证服务是否正常运行

#### 方法1：浏览器测试

1. 打开浏览器
2. 访问：`http://localhost:5019`
3. **应该看到**：`404 Not Found` 或类似错误页面
   - **这是正常的**！说明服务正在运行
   - 因为根路径 `/` 没有配置路由

#### 方法2：命令行测试

**打开另一个命令行窗口**（不要关闭运行服务的窗口），执行：

```bash
curl http://localhost:5019
```

**或者使用 PowerShell**：
```powershell
Invoke-WebRequest -Uri http://localhost:5019
```

**应该看到**：HTTP 响应（可能是 404，这是正常的）

#### 方法3：测试 API 接口

**在另一个命令行窗口执行**：

```bash
curl -X POST http://localhost:5019/api/memory/search -H "Authorization: Bearer your-api-key" -H "Content-Type: application/json" -d "{\"user_id\":\"test\",\"query\":\"test\"}"
```

**如果看到 JSON 响应**（即使是错误），说明服务正常运行

---


## 第五步：在 n8n 平台安装插件

### 5.1 前提条件

**假设**：你已经安装并运行了 n8n 平台

- 本地 n8n：访问 `http://localhost:5678`
- 云端 n8n：访问你的 n8n Cloud 地址

### 5.2 使用 HTTP Request 节点（推荐）

**说明**：实际上，你**不需要安装任何插件**。n8n 自带的 **HTTP Request** 节点就可以直接调用记忆管理 API。

**步骤**：
1. 在 n8n 中创建工作流
2. 添加 **HTTP Request** 节点
3. 配置 API 地址和参数（见第六步）

### 5.3 验证服务连接

**步骤1：确保服务正在运行**

在另一个命令行窗口检查服务是否运行：
```bash
netstat -ano | findstr :5019
```

如果看到端口被占用，说明服务正在运行。

**步骤2：测试连接**

在 n8n 中创建一个简单的测试工作流：

1. 创建新工作流
2. 添加 **HTTP Request** 节点
3. 配置：
   - **Method**：`GET`
   - **URL**：`http://localhost:5019`（如果 n8n 和 app.py 在同一台机器）
   - 或 `http://你的服务器IP:5019`（如果 n8n 在云端）
4. 执行工作流

**如果看到响应**（即使是 404），说明连接正常。

---

## 工作流程图解

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户/外部系统                              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │    n8n 工作流平台      │
            │  (你的 n8n 实例)       │
            │   http://localhost:5678│
            └───────────┬────────────┘
                        │
                        │ HTTP 请求
                        │ (localhost:5019)
                        ▼
        ┌───────────────────────────────┐
        │   n8ndemo 记忆管理服务         │
        │   (主机上运行)                 │
        │   http://localhost:5019       │
        │                                │
        │  ┌──────────────────────────┐ │
        │  │  Flask API 服务           │ │
        │  │  - /api/memory/search     │ │
        │  │  - /api/memory/add        │ │
        │  │  - /api/memory/add_multimodal│
        │  └───────────┬──────────────┘ │
        │              │                 │
        │              ▼                 │
        │  ┌──────────────────────────┐ │
        │  │  Memcontext 记忆系统      │ │
        │  │  - 短期记忆 (7条)         │ │
        │  │  - 中期记忆 (200条)       │ │
        │  │  - 长期知识 (1000条)      │ │
        │  └───────────┬──────────────┘ │
        │              │                 │
        │              ▼                 │
        │  ┌──────────────────────────┐ │
        │  │  数据存储                 │ │
        │  │  n8ndemo/data/            │ │
        │  └──────────────────────────┘ │
        └────────────────────────────────┘
                        │
                        │ 调用
                        ▼
        ┌───────────────────────────────┐
        │   外部服务                     │
        │  - LLM API (OpenAI/火山引擎)   │
        │  - Embedding API              │
        │  - SiliconFlow (音频转录)      │
        └───────────────────────────────┘
```

### 记忆检索工作流程

```
用户提问
   │
   ▼
┌─────────────────┐
│  n8n Webhook    │  接收用户问题
│  节点            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP Request   │  调用记忆检索接口
│  节点            │  POST /api/memory/search
└────────┬────────┘
         │
         │ 请求参数:
         │ {
         │   "user_id": "user123",
         │   "query": "用户之前提到过什么？"
         │ }
         ▼
┌─────────────────┐
│  n8ndemo 服务   │  处理请求
│  /api/memory/   │
│  search         │
└────────┬────────┘
         │
         │ 1. 查找相关记忆
         │ 2. 调用 LLM 生成回复
         ▼
┌─────────────────┐
│  返回结果       │  {
│                 │    "code": 200,
│                 │    "data": {
│                 │      "response": "根据记忆..."
│                 │    }
│                 │  }
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  返回给用户     │  显示回复
└─────────────────┘
```

### 添加记忆工作流程

```
用户对话
   │
   ▼
┌─────────────────┐
│  n8n 工作流     │  捕获对话内容
│  节点            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP Request   │  调用添加记忆接口
│  节点            │  POST /api/memory/add
└────────┬────────┘
         │
         │ 请求参数:
         │ {
         │   "user_id": "user123",
         │   "user_input": "我喜欢喝咖啡",
         │   "agent_response": "好的，我记住了"
         │ }
         ▼
┌─────────────────┐
│  n8ndemo 服务   │  处理请求
│  /api/memory/   │
│  add            │
└────────┬────────┘
         │
         │ 1. 添加到短期记忆
         │ 2. 如果短期记忆满，自动处理到中期记忆
         │ 3. 生成嵌入向量
         ▼
┌─────────────────┐
│  记忆存储       │  n8ndemo/data/users/user123/
│                 │  - short_term.json
│                 │  - mid_term.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  返回结果       │  {
│                 │    "code": 200,
│                 │    "data": {
│                 │      "success": true,
│                 │      "short_term_count": 1
│                 │    }
│                 │  }
└─────────────────┘
```

### 视频处理工作流程

```
视频文件
   │
   ▼
┌─────────────────┐
│  n8n Code 节点  │  设置视频路径
│                 │  file_path: "D:\\...\\video.mp4"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP Request   │  调用视频处理接口
│  节点            │  POST /api/memory/add_multimodal
└────────┬────────┘
         │
         │ 请求参数:
         │ {
         │   "user_id": "user123",
         │   "file_path": "D:\\...\\video.mp4",
         │   "converter_type": "video"
         │ }
         ▼
┌─────────────────┐
│  n8ndemo 服务   │  处理视频
│  /api/memory/   │
│  add_multimodal │
└────────┬────────┘
         │
         │ 处理步骤:
         │ 1. 提取视频帧 (0-20%)
         │ 2. 提取音频 (20-40%)
         │ 3. 音频转录 (40-60%)
         │ 4. 分析视频内容 (60-80%)
         │ 5. 生成嵌入向量 (80-90%)
         │ 6. 存储到记忆系统 (90-100%)
         ▼
┌─────────────────┐
│  返回结果       │  {
│                 │    "code": 200,
│                 │    "data": {
│                 │      "success": true,
│                 │      "ingested_rounds": 5,
│                 │      "progress": [...]
│                 │    }
│                 │  }
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  后续检索       │  可以搜索视频内容
└─────────────────┘
```

### 完整对话流程示例

```
【第一次对话】
用户: "我喜欢喝咖啡"
   │
   ▼
┌─────────────────┐
│  n8n 工作流     │
│  1. 接收输入    │
│  2. 调用 LLM    │  生成回复: "好的，我记住了"
│  3. 添加记忆    │  POST /api/memory/add
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  记忆已保存     │  短期记忆: 1条
└─────────────────┘

【几天后】

用户: "我之前说过我喜欢什么？"
   │
   ▼
┌─────────────────┐
│  n8n 工作流     │
│  1. 接收问题    │
│  2. 检索记忆    │  POST /api/memory/search
│  3. 查找相关记忆│  找到: "我喜欢喝咖啡"
│  4. 调用 LLM    │  生成回复: "根据之前的对话，你提到过你喜欢喝咖啡"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  返回给用户     │  "根据之前的对话，你提到过你喜欢喝咖啡"
└─────────────────┘
```

### 数据流向图

```
┌──────────────┐
│  用户输入    │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────┐
│         n8n 工作流                  │
│                                     │
│  ┌──────────┐    ┌──────────────┐  │
│  │ Webhook  │───▶│ HTTP Request│  │
│  │ 节点      │    │ 节点          │  │
│  └──────────┘    └──────┬───────┘  │
│                         │          │
└─────────────────────────┼──────────┘
                          │
                          │ HTTP POST
                          │ Authorization: Bearer <key>
                          ▼
┌─────────────────────────────────────┐
│      n8ndemo 服务 (Flask)           │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  API 路由处理                │  │
│  │  - 验证 API Key              │  │
│  │  - 解析请求参数              │  │
│  └───────────┬──────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │  Memcontext 记忆系统          │  │
│  │                              │  │
│  │  ┌────────────────────────┐  │  │
│  │  │ 短期记忆 (7条)          │  │  │
│  │  │ - 最新对话              │  │  │
│  │  │ - 快速访问              │  │  │
│  │  └────────────────────────┘  │  │
│  │                              │  │
│  │  ┌────────────────────────┐  │  │
│  │  │ 中期记忆 (200条)        │  │  │
│  │  │ - 近期重要信息          │  │  │
│  │  │ - 热度计算              │  │  │
│  │  └────────────────────────┘  │  │
│  │                              │  │
│  │  ┌────────────────────────┐  │  │
│  │  │ 长期知识 (1000条)       │  │  │
│  │  │ - 永久存储              │  │  │
│  │  │ - 用户画像              │  │  │
│  │  └────────────────────────┘  │  │
│  └───────────┬──────────────────┘  │
│              │                      │
│              │ 调用外部 API         │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │  LLM API                     │  │
│  │  - 生成回复                  │  │
│  │  - 分析内容                  │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Embedding API                │  │
│  │  - 生成向量                  │  │
│  │  - 相似度搜索                │  │
│  └──────────────────────────────┘  │
│                                     │
└───────────────┬─────────────────────┘
                │
                │ JSON 响应
                ▼
┌─────────────────────────────────────┐
│        返回给 n8n                   │
│        {                            │
│          "code": 200,               │
│          "data": { ... }            │
│        }                            │
└─────────────────────────────────────┘
```

---

## 第六步：在 n8n 中创建工作流（详细版）

### 6.1 创建新工作流

**步骤1：打开 n8n**

访问：`http://localhost:5678` 并登录

**步骤2：创建工作流**

1. 点击左侧菜单的 **Workflows**
2. 点击右上角的 **+ Add workflow** 按钮
3. 会打开一个新的工作流编辑器

### 6.2 创建记忆检索工作流

#### 步骤1：添加 Manual Trigger 节点

1. 在工作流编辑器中，点击 **+** 按钮
2. 搜索 "Manual" 或 "Trigger"
3. 选择 **Manual Trigger** 节点
4. 点击添加到画布

**节点说明**：这个节点用于手动触发工作流，方便测试

#### 步骤2：添加 HTTP Request 节点

1. 点击 **+** 按钮
2. 搜索 "HTTP"
3. 选择 **HTTP Request** 节点
4. 点击添加到画布
5. 将 Manual Trigger 节点的输出连接到 HTTP Request 节点

#### 步骤3：配置 HTTP Request 节点

**点击 HTTP Request 节点**，在右侧配置面板设置：

**1. 基本设置**：
- **Method**：选择 `POST`
- **URL**：
  - **URL**：`http://localhost:5019/api/memory/search`（如果 n8n 和 app.py 在同一台机器）
  - 或 `http://你的服务器IP:5019/api/memory/search`（如果 n8n 在云端）

**2. Authentication**：
- 点击 **Authentication** 下拉菜单
- 选择 **Generic Credential Type**
- 选择 **Bearer Token**
- 在 **Token** 字段输入：你在 `.env` 文件中设置的 `N8N_API_KEYS` 的值
  - 例如：`my-secret-key-12345`

**3. Headers**：
- 点击 **Add Header** 或 **Send Headers** 开关
- 添加 Header：
  - **Name**：`Content-Type`
  - **Value**：`application/json`

**4. Body**：
- 找到 **Specify Body** 或 **Send Body** 选项
- 选择 **JSON**
- 在 JSON 框中输入：
  ```json
  {
    "user_id": "test_user",
    "query": "用户之前提到过什么？",
    "relationship_with_user": "friend",
    "style_hint": "友好"
  }
  ```

**5. Options（重要）**：
- 展开 **Options** 部分
- 找到 **Timeout** 选项
- 设置为 `30000`（30 秒，单位：毫秒）
  - 对于视频处理，建议设置为 `1800000`（30 分钟）

**6. 保存配置**：
- 点击右上角的 **Save** 按钮

#### 步骤4：执行测试

1. 点击 **Manual Trigger** 节点
2. 点击右上角的 **Execute Workflow** 按钮
3. 等待执行完成
4. 点击 **HTTP Request** 节点，查看输出

**成功输出示例**：
```json
{
  "code": 200,
  "message": "操作成功",
  "errorCode": 0,
  "data": {
    "response": "根据记忆，用户之前提到过...",
    "timestamp": "2024-01-01T12:00:00"
  }
}
```

### 6.3 创建添加记忆工作流

#### 步骤1：创建工作流

按照 6.2 的步骤创建新工作流，或修改现有工作流

#### 步骤2：配置 HTTP Request 节点

**基本设置**：
- **Method**：`POST`
- **URL**：`http://localhost:5019/api/memory/add`

**Authentication**：同上（Bearer Token）

**Body (JSON)**：
```json
{
  "user_id": "test_user",
  "user_input": "我喜欢喝咖啡",
  "agent_response": "好的，我记住了你喜欢喝咖啡"
}
```

#### 步骤3：执行测试

执行工作流，应该看到成功响应：
```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "success": true,
    "message": "记忆已添加到短期记忆",
    "short_term_count": 1,
    "is_full": false
  }
}
```

### 6.4 创建视频上传工作流

#### 方式1：使用自动化脚本（推荐）

项目提供了自动化脚本，可以快速创建工作流：

**步骤1：运行脚本**

在项目根目录执行：
```bash
create_video_workflow.bat
```

或者：
```bash
python create_video_workflow.py
```

**步骤2：脚本会自动**：
- ✅ 创建工作流
- ✅ 配置所有节点
- ✅ 激活工作流

**步骤3：在 n8n 中查看**

1. 打开 n8n：`http://localhost:5678`
2. 找到工作流："视频上传和检索工作流"
3. 点击打开，查看配置

#### 方式2：手动创建工作流

详细步骤请参考 6.2 和 6.3 的说明，配置视频上传相关的节点。

---

## 完整测试流程

### 测试前准备

1. ✅ **确保 n8ndemo 服务正在运行**
   ```bash
   # 检查服务是否运行
   netstat -ano | findstr :5019
   ```
   如果看到端口被占用，说明服务正在运行

2. ✅ **确保 n8n 正在运行**
   - 访问 `http://localhost:5678` 能正常打开

3. ✅ **确保 `.env` 文件已配置**
   - 检查项目根目录是否有 `.env` 文件
   - 确认 `N8N_API_KEYS` 和 `LLM_API_KEY` 已填写

### 测试方法1：在 n8n 中手动测试

**步骤1：创建测试工作流**

按照 6.2 的步骤创建记忆检索工作流

**步骤2：执行工作流**

1. 点击 "Manual Trigger" 节点
2. 点击 "Execute Workflow"
3. 查看执行结果

**步骤3：验证结果**

- ✅ 如果看到 `"code": 200`，说明测试成功
- ❌ 如果看到错误，参考"常见问题详细排查"章节

### 测试方法2：使用 curl 命令

**测试记忆检索**：
```bash
curl -X POST http://localhost:5019/api/memory/search ^
  -H "Authorization: Bearer your-api-key" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"test_user\",\"query\":\"测试问题\"}"
```

**测试添加记忆**：
```bash
curl -X POST http://localhost:5019/api/memory/add ^
  -H "Authorization: Bearer your-api-key" ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"test_user\",\"user_input\":\"测试输入\",\"agent_response\":\"测试回复\"}"
```

### 测试检查清单

完成以下测试，确保所有功能正常：

- [ ] **基础连接测试**：服务能正常启动
- [ ] **API Key 验证**：使用正确的 API Key 能访问，错误的被拒绝
- [ ] **记忆检索**：能成功检索记忆并返回结果
- [ ] **添加记忆**：能成功添加记忆到系统
- [ ] **视频处理**：能成功处理视频文件（如果测试了视频功能）
- [ ] **错误处理**：缺少参数时返回正确的错误信息

---

## 常见问题详细排查

### 环境配置问题

#### Q1: 启动服务时提示 "ModuleNotFoundError: No module named 'flask'"

**原因**：缺少 Python 依赖包

**解决方法**：
```bash
pip install flask python-dotenv requests
```

或者使用 requirements.txt：
```bash
pip install -r requirements.txt
```

#### Q2: 提示 "LLM_API_KEY 环境变量未配置"

**原因**：`.env` 文件配置不正确或未加载

**解决方法**：
1. 检查 `.env` 文件是否在项目**根目录**（不是 n8ndemo 目录）
2. 检查 `.env` 文件中的 `LLM_API_KEY` 是否正确填写
3. 确保 `.env` 文件格式正确（没有多余的空格或引号）
4. 重启服务

#### Q3: 端口被占用

**错误信息**：
```
OSError: [WinError 10048] 通常每个套接字地址(协议/网络地址/端口)只允许使用一次
```

**解决方法**：
1. 检查端口是否被占用：
   ```bash
   netstat -ano | findstr :5019
   ```
2. 如果看到进程 ID（最后一列），结束该进程：
   ```bash
   taskkill /PID <进程ID> /F
   ```
3. 或者修改 `app.py` 中的端口号（不推荐）

### 网络连接问题

#### Q4: n8n 无法连接到 n8ndemo 服务

**错误信息**：
```
The connection to the server was closed unexpectedly
Connection refused
```

**解决方法**：
1. **确保 n8ndemo 服务正在运行**：
   ```bash
   netstat -ano | findstr :5019
   ```
   如果看不到端口被占用，说明服务未启动

2. **检查 URL 配置**：
   - 如果 n8n 和 app.py 在同一台机器：使用 `http://localhost:5019`
   - 如果 n8n 在云端，app.py 在本地：需要配置端口转发或使用公网 IP

3. **如果 localhost 不可用**：
   ```bash
   ipconfig  # 查看 IPv4 地址，例如 192.168.1.100
   ```
   然后在 n8n 中使用：`http://192.168.1.100:5019`

### API 调用问题

#### Q5: "Bad request - please check your parameters"

**原因**：请求参数不正确

**解决方法**：
1. 检查请求的 JSON 格式是否正确
2. 检查必需参数是否都提供了：
   - `/api/memory/add` 需要：`user_id`, `user_input`, `agent_response`
   - `/api/memory/search` 需要：`user_id`, `query`
   - `/api/memory/add_multimodal` 需要：`user_id`, `file_path`
3. 检查参数名称是否正确（区分大小写）

#### Q6: "No converter registered for type=videorag"

**原因**：转换器类型配置错误

**解决方法**：
- 使用 `"converter_type": "video"` 而不是 `"videorag"`

#### Q7: 视频处理超时

**原因**：视频文件太大，处理时间超过超时限制

**解决方法**：
1. 在 n8n HTTP Request 节点中增加超时时间
2. 建议设置为 30 分钟（1800000 毫秒）或更长
3. 大视频文件需要更长时间，请耐心等待

#### Q8: 文件路径找不到

**原因**：路径格式错误或文件不存在

**解决方法**：
1. 使用**绝对路径**，例如：`D:\\project\\memcontext-memcontext\\n8ndemo\\test1.mp4`
2. Windows 路径使用双反斜杠 `\\` 或正斜杠 `/`
3. 确保文件确实存在
4. 注意：使用 Windows 绝对路径

### 其他问题

#### Q9: 服务启动后立即退出

**原因**：可能是端口被占用或配置错误

**解决方法**：
1. 检查端口 5019 是否被占用：
   ```bash
   netstat -ano | findstr :5019
   ```
2. 如果被占用，停止占用端口的程序或修改 `app.py` 中的端口号
3. 检查 `.env` 文件配置是否正确

#### Q10: 如何查看详细的错误信息？

**方法1：查看服务日志**
- 在运行 `python app.py` 的命令行窗口查看输出

**方法2：查看 n8n 节点输出**
- 在 n8n 工作流中，点击每个节点查看输入/输出数据
- 查看 "Executions" 页面查看执行历史


---