# MemContext n8n Plugin

<div align="center">

**Multimodal Agent Memory Service for n8n Workflows**

Empower your n8n workflows with persistent memory capabilities, supporting text, video, audio, images, and other modalities.

</div>

## 📖 Introduction

The MemContext n8n Plugin is an n8n plugin service developed based on the MemContext Multimodal Agent Memory Framework. It provides powerful memory management capabilities to n8n workflows via a RESTful API, enabling your automation workflows to achieve:

- 🧠 **Persistent Memory**: Save and retrieve conversation history to build long-term user profiles.
- 🎬 **Multimodal Processing**: Support content understanding for various formats including video, audio, images, and documents.
- 🔍 **Smart Retrieval**: Precise memory retrieval based on semantic similarity.
- ⚡ **Plug & Play**: No complex configuration required; call it directly using the HTTP Request node.

## Core Features

- ✅ **Three-Layer Memory Architecture**: Short-term memory, medium-term memory, and long-term knowledge base.
- ✅ **Multimodal Support**: Unified processing for text, video, audio, images, and documents.
- ✅ **RESTful API**: Standard HTTP interfaces for easy integration.
- ✅ **User Isolation**: Multi-user memory management based on user_id.
- ✅ **Secure Authentication**: Bearer Token authentication mechanism.

## 📋 Prerequisites

### System Requirements

Before you begin, please ensure your environment meets the following requirements:

| Component | Requirement | Description |
|-----------|-------------|-------------|
| Python | 3.10+ | Runs the plugin backend service |
| FFmpeg | Latest | Used for audio/video stream processing |
| Docker | Latest | Used for quick deployment of n8n instances |
| n8n | v1.0+ | Automation workflow platform |

## 🚀 Quick Start

### Step 1: Environment Configuration

#### 1.1 Create Python Virtual Environment

```bash
conda create -n memcontext-n8n python=3.10 -y
conda activate memcontext-n8n
```

#### 1.2 Install Dependencies

```bash
# Run in the MemContext project root directory
pip install -r requirements.txt
pip install -r ./memcontext-n8n/requirements.txt

# If using ByteDance Volcengine models, install the following:
pip install volcengine-python-sdk[ark]
```

#### 1.3 Install System Dependencies

```bash
# Windows
winget install FFmpeg
ffmpeg -version

winget install Docker.DockerDesktop
docker --version
```

### Step 2: Start n8n Service

#### 2.1 Start n8n using Docker (Recommended)

```bash
# Enter the memcontext-n8n directory
cd memcontext-n8n

# Run the Docker startup script
docker-run-n8n.bat
```

The script will automatically check Docker status and port availability, then start the n8n container and mount local directories.

#### 2.2 Access n8n

Visit http://localhost:5678 and log in.

### Step 3: Configure Environment Variables

Create a `.env` file in the `memcontext-n8n` directory. Example configuration:

```env
# ============================================
# LLM API Configuration (Required)
# ============================================
LLM_API_KEY=YOUR-API-KEY
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-1-6-flash-250828

# ============================================
# Embedding API Configuration (For Vector Database)
# ============================================
EMBEDDING_API_KEY=YOUR-API-KEY
EMBEDDING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EMBEDDING_MODEL=doubao-embedding-large-text-250515

# ============================================
# SiliconFlow API Configuration (Optional, for Audio Transcription)
# ============================================
SILICONFLOW_API_KEY=YOUR-API-KEY
SILICONFLOW_MODEL=TeleAI/TeleSpeechASR
ENABLE_AUDIO_TRANSCRIPTION=true

# ============================================
# n8n API Key (Required, for Service Authentication)
# ============================================
# Create an API Key in n8n via Settings (bottom left) → n8n API
N8N_API_KEY=YOUR-API-KEY
```

### Step 4: Start MemContext-n8n Plugin Service

```bash
cd memcontext-n8n
python app.py
```

The service will start at http://localhost:5019.

**Verify Service Operation:**

```bash
# Check port usage
netstat -ano | findstr :5019

# Or test using curl
curl http://localhost:5019
```

### Step 5: Create Workflow Example

#### 5.1 Create Video Memory Workflow Demo

Run the following commands. The script will automatically create a video upload and retrieval workflow demo and configure all nodes.

```bash
cd memcontext-n8n

# Run the workflow creation script
create_video_workflow.bat
```

Prepare a video of about 1 minute (if the video is too long, processing time may be significant) and place it in the `memcontext-n8n/memcontext-n8n` directory.

#### 5.2 Execute Workflow in n8n

1. Visit http://localhost:5678
2. Find "Video Upload and Retrieval Workflow"
3. Click "Execute Workflow" to run
4. View the execution results

**Expected Output:**

You can see a visualization of the entire process below:

- `video_upload.success`: `true`
- `memory_search.success`: `true`
- `summary.answer`: Contains a description of the video content

## 📜 License

This project is licensed under the Apache-2.0 License.
