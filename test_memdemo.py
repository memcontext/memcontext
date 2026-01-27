#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
示例：给 memdemo Flask 项目提交视频并触发 VideoRAG 记忆同步

注意：现在使用 FileStorageManager 统一管理视频文件存储
- 视频文件会自动上传到 FileStorageManager
- working_dir 由 FileStorageManager 自动管理，无需手动指定
- 文件存储在 storage_base_path/files/videos/{file_id}/（默认在项目根目录的 files 下）
- VideoRAG 处理时的视频片段存储在 working_dir/_cache/{video_name}/ 目录下
"""

import json
import pathlib
import requests
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 从项目根目录查找 .env 文件（假设 test_memdemo.py 在项目根目录）
load_dotenv()

SERVER = "http://127.0.0.1:5019"
SESSION_INIT_ENDPOINT = f"{SERVER}/init_memory"
ADD_MM_ENDPOINT = f"{SERVER}/add_multimodal_memory"

def init_memory(session):
    # 豆包配置从环境变量读取，无需传递
    payload = {
        "user_id": "video_user7",
    }
    resp = session.post(SESSION_INIT_ENDPOINT, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"初始化失败: {data}")
    return data["session_id"]

def add_video(session, video_path, auto_summary=False, working_dir=None):
    """
    添加视频到记忆系统
    
    Args:
        session: requests.Session 对象
        video_path: 视频文件路径
        auto_summary: 是否自动生成视频总结
        working_dir: 工作目录（可选，如果不提供则使用 FileStorageManager 管理的路径）
    """
    converter_kwargs = {
        "auto_summary": auto_summary,
    }
    
    # 如果指定了 working_dir，则使用它（回退到旧的行为）
    # 否则使用 FileStorageManager 自动管理的路径
    if working_dir:
        converter_kwargs["working_dir"] = working_dir
        print(f"使用指定的 working_dir: {working_dir}")
    else:
        print("使用 FileStorageManager 自动管理的存储路径")
    
    payload = {
        "converter_type": "videorag",
        "converter_kwargs": json.dumps(converter_kwargs)
    }
    files = {
        "file": (pathlib.Path(video_path).name, open(video_path, "rb"), "video/mp4")
    }
    resp = session.post(
        ADD_MM_ENDPOINT,
        data=payload,
        files=files,
        timeout=24000,  # VideoRAG 处理较耗时
    )
    print(resp.text)
    resp.raise_for_status()
    return resp.json()

def main():
    session = requests.Session()
    session_id = init_memory(session)
    print(f"Session ready: {session_id}")

    # result = add_video(session=session, video_path="/root/repo/uni-mem/files/test_video.mp4")
    result = add_video(
        session=session, 
        video_path="/root/repo/uni-mem/files/BigBuckBunny_320x180.mp4",
        auto_summary=False
    )
    
    print("\n" + "="*60)
    print("处理结果:")
    print("="*60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 如果返回了 file_id，说明文件已通过 FileStorageManager 管理
    if result.get('file_id'):
        print(f"\n文件已通过 FileStorageManager 管理")
        print(f"file_id: {result.get('file_id')}")
        # 显示实际存储路径
        if result.get('storage_path'):
            print(f"存储路径: {result.get('storage_path')}/")
        elif result.get('storage_base_path'):
            print(f"存储路径: {result.get('storage_base_path')}/files/videos/{result.get('file_id')}/")
        else:
            # 如果没有返回路径信息，提示默认位置
            print(f"存储路径: /root/repo/memcontext-dev/files/videos/{result.get('file_id')}/ (默认位置)")
    
    # 如果需要使用自定义 working_dir（不推荐，仅用于测试）
    # result = add_video(
    #     session=session, 
    #     video_path="/root/repo/uni-mem/files/BigBuckBunny_320x180.mp4",
    #     working_dir="./videorag-workdir"
    # )

if __name__ == "__main__":
    main()
