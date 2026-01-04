#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建支持视频上传和检索的 n8n 工作流
工作流包含：
1. 手动触发（可输入视频文件路径）
2. 添加视频记忆（multimodal）
3. 搜索记忆
4. 输出结果
"""

import requests
import json
import time
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 配置
N8N_URL = "http://localhost:5678"
N8N_USER = "admin"
N8N_PASS = "admin"
API_URL = "http://host.docker.internal:5019"

# 读取 n8n API Key（用于调用 n8n API）
N8N_API_KEY = os.environ.get("N8N_API_KEY", "").strip()
# 清理可能的换行符和多余空格
if N8N_API_KEY:
    N8N_API_KEY = N8N_API_KEY.replace('\n', '').replace('\r', '').strip()

# 读取 memcontext API Key（用于调用 memcontext API）
api_keys_str = os.environ.get("N8N_API_KEYS", "").strip()
if api_keys_str:
    MEMCONTEXT_API_KEY = api_keys_str.split(',')[0].strip()
else:
    MEMCONTEXT_API_KEY = os.environ.get("N8N_API_KEY", "test-key")

print("=" * 60)
print("创建视频上传和检索工作流")
print("=" * 60)
print(f"\n配置:")
print(f"  n8n URL: {N8N_URL}")
print(f"  API URL: {API_URL}")
print(f"  Memcontext API Key: {MEMCONTEXT_API_KEY[:10]}...")
if N8N_API_KEY:
    print(f"  n8n API Key: {N8N_API_KEY[:20]}... (已配置，长度: {len(N8N_API_KEY)})")
else:
    print(f"  n8n API Key: 未配置，将使用 Basic Auth")
print()

# 创建工作流
print("[1/4] 创建工作流...")
workflow_data = {
    "name": "视频上传和检索工作流",
    "nodes": [
        {
            "parameters": {},
            "id": "start",
            "name": "当点击测试时",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [250, 300]
        },
        {
            "parameters": {
                "jsCode": "// 设置视频文件路径\n// 注意：n8n 在 Docker 中运行，但 n8ndemo 服务在主机上运行（通过 host.docker.internal:5019 访问）\n// 所以需要使用 Windows 路径（主机路径），因为服务在主机上读取文件\n// 方法1: 从输入数据获取 video_path（如果手动触发时提供了）\n// 方法2: 使用默认路径（Windows 路径）\nconst inputData = $input.item.json || {};\n\n// 使用 Windows 路径（因为 n8ndemo 服务在主机上运行）\nconst videoPath = inputData.video_path || 'D:\\\\project\\\\memcontext-memcontext\\\\n8ndemo\\\\test1.mp4';\n\n// 如果路径包含引号，自动去除\nconst cleanPath = videoPath.replace(/^[\"']|[\"']$/g, '');\n\n// 验证路径格式\nif (!cleanPath || cleanPath.trim() === '') {\n  throw new Error('视频路径不能为空');\n}\n\nreturn {\n  json: {\n    file_path: cleanPath,\n    user_id: inputData.user_id || 'test_user_video',\n    agent_response: inputData.agent_response || '已上传视频并添加到记忆',\n    converter_type: inputData.converter_type || 'video',\n    query: inputData.query || '这个视频主要讲的是什么内容？'\n  }\n};"
            },
            "id": "set_video_path",
            "name": "设置视频路径",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [450, 300]
        },
        {
            "parameters": {
                "url": f"{API_URL}/api/memory/add_multimodal",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {
                            "name": "Authorization",
                            "value": f"Bearer {MEMCONTEXT_API_KEY}"
                        },
                        {
                            "name": "Content-Type",
                            "value": "application/json"
                        }
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({\n  user_id: $json.user_id,\n  file_path: $json.file_path,\n  agent_response: $json.agent_response,\n  converter_type: $json.converter_type\n}) }}",
                "options": {
                    "timeout": 1800000,
                    "response": {
                        "response": {
                            "neverError": True,
                            "responseFormat": "json"
                        }
                    },
                    "redirect": {
                        "redirect": {
                            "followRedirects": True
                        }
                    }
                }
            },
            "id": "add_video_memory",
            "name": "添加视频记忆",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [650, 300]
        },
        {
            "parameters": {
                "url": f"{API_URL}/api/memory/search",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {
                            "name": "Authorization",
                            "value": f"Bearer {MEMCONTEXT_API_KEY}"
                        },
                        {
                            "name": "Content-Type",
                            "value": "application/json"
                        }
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({\n  user_id: $('设置视频路径').item.json.user_id,\n  query: $('设置视频路径').item.json.query || '这个视频主要讲的是什么内容？',\n  relationship_with_user: 'friend',\n  style_hint: '友好'\n}) }}",
                "options": {}
            },
            "id": "search_memory",
            "name": "搜索记忆",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [850, 300]
        },
        {
            "parameters": {
                "jsCode": "// 格式化输出结果\nconst addResult = $('添加视频记忆').item.json || {};\nconst searchResult = $('搜索记忆').item.json || {};\n\n// 提取关键信息\nconst uploadSuccess = addResult.code === 200 || addResult.code === undefined;\nconst searchSuccess = searchResult.code === 200 || searchResult.code === undefined;\n\nreturn {\n  json: {\n    video_upload: {\n      success: uploadSuccess,\n      message: addResult.message || '视频处理完成',\n      data: addResult.data || addResult,\n      ingested_rounds: addResult.data?.ingested_rounds || 0,\n      file_id: addResult.data?.file_id || null\n    },\n    memory_search: {\n      success: searchSuccess,\n      message: searchResult.message || '搜索完成',\n      response: searchResult.data?.response || searchResult.response || '未找到相关记忆',\n      timestamp: searchResult.data?.timestamp || null\n    },\n    summary: {\n      video_processed: uploadSuccess ? '成功' : '失败',\n      memory_found: searchSuccess && (searchResult.data?.response || searchResult.response) ? '是' : '否',\n      answer: searchResult.data?.response || searchResult.response || '未找到相关记忆',\n      chunks_ingested: addResult.data?.ingested_rounds || 0\n    }\n  }\n};"
            },
            "id": "format_output",
            "name": "格式化输出",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1050, 300]
        }
    ],
    "connections": {
        "当点击测试时": {
            "main": [[{"node": "设置视频路径", "type": "main", "index": 0}]]
        },
        "设置视频路径": {
            "main": [[{"node": "添加视频记忆", "type": "main", "index": 0}]]
        },
        "添加视频记忆": {
            "main": [[{"node": "搜索记忆", "type": "main", "index": 0}]]
        },
        "搜索记忆": {
            "main": [[{"node": "格式化输出", "type": "main", "index": 0}]]
        }
    },
    "settings": {},
    "staticData": None
}

# 准备请求头
headers = {}
if N8N_API_KEY:
    headers["X-N8N-API-KEY"] = N8N_API_KEY
    auth = None
else:
    # 使用 Basic Auth
    from requests.auth import HTTPBasicAuth
    auth = HTTPBasicAuth(N8N_USER, N8N_PASS)

try:
    # 调试：显示实际使用的认证方式
    if N8N_API_KEY:
        print(f"[调试] 使用 API Key 认证，Key 前20字符: {N8N_API_KEY[:20]}...")
        print(f"[调试] 请求头: X-N8N-API-KEY = {N8N_API_KEY[:30]}...")
    else:
        print(f"[调试] 使用 Basic Auth: {N8N_USER}/{N8N_PASS}")
    
    response = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        json=workflow_data,
        headers=headers,
        auth=auth if not N8N_API_KEY else None,
        timeout=10
    )
    
    if response.status_code in [200, 201]:
        workflow = response.json()
        workflow_id = workflow["id"]
        print(f"[成功] 工作流已创建，ID: {workflow_id}")
    else:
        print(f"[错误] 创建工作流失败: {response.status_code}")
        print(response.text)
        if response.status_code == 401:
            print(f"\n[调试] 当前使用的 API Key: {N8N_API_KEY[:50] if N8N_API_KEY else '未配置'}...")
            print(f"[调试] 请检查 .env 文件中的 N8N_API_KEY 是否正确")
            print("\n提示: n8n 需要 API Key 认证")
            print("请按以下步骤获取 API Key:")
            print("1. 打开浏览器访问: http://localhost:5678")
            print("2. 进入 Settings -> API")
            print("3. 创建新的 API Key")
            print("4. 在 .env 文件中添加: N8N_API_KEY=你的API密钥")
        exit(1)
except Exception as e:
    print(f"[错误] 创建失败: {e}")
    exit(1)

# 2. 等待工作流就绪
print("\n[2/4] 等待工作流就绪...")
time.sleep(2)

# 3. 激活工作流
print("[3/4] 激活工作流...")
try:
    # n8n 激活工作流需要发送 active: true
    response = requests.post(
        f"{N8N_URL}/api/v1/workflows/{workflow_id}/activate",
        json={"active": True},
        headers=headers,
        auth=auth if not N8N_API_KEY else None,
        timeout=10
    )
    if response.status_code in [200, 204]:
        print("[成功] 工作流已激活")
    else:
        print(f"[警告] 激活失败: {response.status_code}")
        print(f"响应: {response.text}")
        print("提示: 可以在 n8n UI 中手动激活工作流")
except Exception as e:
    print(f"[警告] 激活失败: {e}")
    print("提示: 可以在 n8n UI 中手动激活工作流")

print("\n" + "=" * 60)
print("工作流创建完成！")
print("=" * 60)
print(f"\n工作流 URL: {N8N_URL}/workflow/{workflow_id}")
print(f"\n使用说明:")
print("1. 在浏览器中打开上面的 URL")
print("2. 点击 '设置视频路径' 节点，修改代码中的视频路径")
print("   或者在工作流执行时，在输入数据中添加 video_path 字段")
print("3. 点击 '当点击测试时' 节点，然后点击 'Execute Workflow' 执行")
print("4. 查看 '格式化输出' 节点的结果")
print("\n提示:")
print("- 视频路径格式: D:\\\\project\\\\memcontext-memcontext\\\\test_video.mp4")
print("- 或者使用正斜杠: D:/project/memcontext-memcontext/test_video.mp4")
print("- 如果路径包含空格，不需要加引号，n8n 会自动处理")

