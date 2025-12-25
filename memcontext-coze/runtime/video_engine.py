"""
视频理解引擎
使用 VideoConverter (豆包视频理解 API) 进行视频理解
"""
import json
import threading
import time
import uuid
import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timedelta

# 添加包含 memcontext 包的目录到路径，以便导入 memcontext
# video_engine.py 在 memcontext-coze/runtime/ 目录
# memcontext 包在 memcontext/memcontext/ 目录
# 需要将 memcontext/ 目录（包含 memcontext 包的父目录）添加到 sys.path
_memcontext_parent_dir = Path(__file__).parent.parent.parent  # memcontext/ 目录
if str(_memcontext_parent_dir) not in sys.path:
    sys.path.insert(0, str(_memcontext_parent_dir))

from memcontext.multimodal.converters.video_converter import VideoConverter


class VideoJobStore:
    """Job 存储管理器"""
    
    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.store_dir / "jobs.json"
        self.lock = threading.Lock()
        self.jobs: Dict[str, Dict] = {}
        self._load_jobs()
    
    def _load_jobs(self):
        """从文件加载 jobs"""
        if self.store_file.exists():
            try:
                with open(self.store_file, 'r', encoding='utf-8') as f:
                    self.jobs = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load jobs: {e}")
                self.jobs = {}
    
    def _save_jobs(self):
        """保存 jobs 到文件"""
        try:
            with open(self.store_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving jobs: {e}")
    
    def create_job(self, video_path: str, options: Dict = None) -> str:
        """创建新 job"""
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                "job_id": job_id,
                "video_path": video_path,
                "status": "queued",
                "progress": 0.0,
                "options": options or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "result": None,
                "error": None
            }
            self._save_jobs()
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取 job"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def find_job_by_path(self, video_path: str, status: str = None) -> Optional[Dict]:
        """根据视频路径查找 job，优先返回指定状态的"""
        with self.lock:
            # 查找所有匹配路径的 job
            matching_jobs = []
            for job_id, job_data in self.jobs.items():
                if job_data.get("video_path") == video_path:
                    matching_jobs.append((job_id, job_data))
            
            if not matching_jobs:
                return None
            
            # 如果有指定状态，优先返回该状态的（按更新时间倒序）
            if status:
                status_matches = [j for j in matching_jobs if j[1].get("status") == status]
                if status_matches:
                    # 按更新时间排序，返回最新的
                    status_matches.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
                    result = status_matches[0][1].copy()
                    result["job_id"] = status_matches[0][0]
                    return result
            
            # 没有指定状态，返回最新的
            matching_jobs.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
            result = matching_jobs[0][1].copy()
            result["job_id"] = matching_jobs[0][0]
            return result
    
    def update_job(self, job_id: str, **kwargs):
        """更新 job"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(kwargs)
                self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
                self._save_jobs()
    
    def cleanup_old_jobs(self, max_age_hours: int = 24, max_count: int = 100):
        """清理旧 job（保留最近 N 个或 24 小时内的）"""
        with self.lock:
            now = datetime.now()
            jobs_to_keep = []
            
            # 按更新时间排序
            sorted_jobs = sorted(
                self.jobs.items(),
                key=lambda x: x[1].get("updated_at", ""),
                reverse=True
            )
            
            for job_id, job_data in sorted_jobs:
                updated_at_str = job_data.get("updated_at", "")
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        age = now - updated_at
                        if age < timedelta(hours=max_age_hours) or len(jobs_to_keep) < max_count:
                            jobs_to_keep.append((job_id, job_data))
                    except:
                        # 如果日期解析失败，保留
                        if len(jobs_to_keep) < max_count:
                            jobs_to_keep.append((job_id, job_data))
                else:
                    if len(jobs_to_keep) < max_count:
                        jobs_to_keep.append((job_id, job_data))
            
            self.jobs = dict(jobs_to_keep)
            self._save_jobs()


class VideoEngine:
    """视频理解引擎 - 基于 VideoConverter (豆包视频理解 API)"""
    
    def __init__(self, store_dir: Path = None):
        """
        初始化视频引擎
        
        Args:
            store_dir: job 存储目录
        """
        if store_dir is None:
            store_dir = Path(__file__).parent / "job_store"
        self.store = VideoJobStore(store_dir)
        
        self.valid_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.flv'}
    
    def validate_video_path(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        验证视频路径
        
        Returns:
            (is_valid, error_message)
        """
        # 检查是否是 UUID 格式（可能是误传的 job_id）
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if re.match(uuid_pattern, path.strip()):
            return False, f"路径看起来像是任务ID（job_id），而不是视频文件路径。请提供实际的视频文件路径（如 /path/to/video.mp4）"
        
        video_path = Path(path)
        
        if not video_path.exists():
            return False, f"视频文件不存在: {path}。请检查路径是否正确"
        
        if not video_path.is_file():
            return False, f"路径不是文件: {path}"
        
        if video_path.suffix.lower() not in self.valid_extensions:
            return False, f"不支持的视频格式: {video_path.suffix}，支持格式: {', '.join(self.valid_extensions)}"
        
        return True, None
    
    def submit_video(self, path: str, options: Dict = None) -> str:
        """
        提交视频处理任务
        
        Returns:
            job_id
        """
        is_valid, error = self.validate_video_path(path)
        if not is_valid:
            raise ValueError(error)
        
        # 检查是否已有相同路径的成功处理结果
        existing_job = self.store.find_job_by_path(path, status="succeeded")
        if existing_job:
            # 如果已有成功的结果，直接返回该 job_id
            return existing_job["job_id"]
        
        job_id = self.store.create_job(path, options)
        
        # 启动后台处理线程
        thread = threading.Thread(
            target=self._process_video_background,
            args=(job_id,),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def get_status(self, job_id: str) -> Dict:
        """获取任务状态"""
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        return {
            "status": job["status"],
            "progress": job["progress"]
        }
    
    def get_result(self, job_id: str) -> Dict:
        """获取任务结果"""
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job["status"] != "succeeded":
            raise ValueError(f"Job {job_id} is not completed, status: {job['status']}")
        
        if not job.get("result"):
            raise ValueError(f"Job {job_id} has no result")
        
        return job["result"]
    
    def _process_video_background(self, job_id: str):
        """后台处理视频 - 使用 VideoConverter (豆包视频理解)"""
        job = self.store.get_job(job_id)
        if not job:
            return
        
        try:
            self.store.update_job(job_id, status="running", progress=0.05)
            
            video_path = Path(job["video_path"])
            options = job.get("options", {})
            
            # 创建进度回调
            def progress_callback(progress: float, message: str):
                # VideoConverter 的进度范围是 0-1，我们映射到 0.05-0.95
                mapped_progress = 0.05 + progress * 0.9
                self.store.update_job(job_id, progress=mapped_progress)
                print(f"[Job {job_id}] {progress*100:.1f}%: {message}")
            
            # 创建 VideoConverter (使用环境变量中的豆包配置)
            converter = VideoConverter(
                progress_callback=progress_callback,
            )
            
            # 调用 converter
            self.store.update_job(job_id, progress=0.1)
            output = converter.convert(
                str(video_path),
                source_type="file_path",
            )
            
            if output.status != "success":
                raise Exception(output.error or "视频处理失败")
            
            self.store.update_job(job_id, progress=0.9)
            
            # 将 ConversionOutput 转换为插件需要的格式
            result = self._convert_output_to_result(output)
            
            self.store.update_job(
                job_id,
                status="succeeded",
                progress=1.0,
                result=result
            )
            
        except Exception as e:
            error_msg = str(e)
            import traceback
            traceback.print_exc()
            print(f"Error processing video {job_id}: {error_msg}")
            self.store.update_job(
                job_id,
                status="failed",
                error=error_msg
            )
    
    def _convert_output_to_result(self, output) -> Dict:
        """将 ConversionOutput 转换为插件需要的格式"""
        # video_converter 返回的所有 chunks 都是 segment chunks
        segment_chunks = output.chunks
        
        # 生成 caption（使用所有 chunks 的文本组合，取前5个）
        if segment_chunks:
            caption = "\n\n".join([chunk.text for chunk in segment_chunks[:5]])
            if len(segment_chunks) > 5:
                caption += f"\n\n...（共 {len(segment_chunks)} 个片段）"
        else:
            caption = "无视频内容描述"
        
        # 生成 tags（基于 metadata）
        tags = self._extract_tags(output, segment_chunks)
        
        # 生成 timeline（基于 segment chunks）
        timeline = self._build_timeline(segment_chunks)
        
        return {
            "caption": caption,
            "tags": tags,
            "timeline": timeline,
            "metadata": output.metadata
        }
    
    def _extract_tags(self, output, segment_chunks: List) -> List[str]:
        """从输出中提取标签"""
        tags = []
        
        # 基于片段数量
        if len(segment_chunks) > 20:
            tags.append("长视频")
        elif len(segment_chunks) > 10:
            tags.append("中等时长")
        else:
            tags.append("短视频")
        
        # 检查是否有音频转录（说明有音频）
        has_audio = False
        for chunk in segment_chunks:
            if chunk.metadata.get("has_audio") or chunk.metadata.get("audio_transcription"):
                has_audio = True
                break
        
        if has_audio:
            tags.append("有音频")
        
        # 从 metadata 中提取其他信息
        if output.metadata.get("converter_provider"):
            tags.append(output.metadata.get("converter_provider"))
        
        return tags
    
    def _build_timeline(self, segment_chunks: List) -> List[Dict]:
        """从 segment chunks 构建 timeline"""
        timeline = []
        
        for chunk in segment_chunks:
            metadata = chunk.metadata
            
            # video_converter 提供 segment_start_time 和 segment_end_time
            start_sec = metadata.get("segment_start_time")
            end_sec = metadata.get("segment_end_time")
            
            # 如果没有，尝试从 time_range 解析（格式如 "00:30-01:30"）
            if start_sec is None or end_sec is None:
                time_range = metadata.get("time_range")
                if time_range:
                    try:
                        # 格式可能是 "00:30-01:30" 或 "0.00-60.00"
                        parts = str(time_range).split("-")
                        if len(parts) == 2:
                            # 尝试解析为秒数格式
                            try:
                                start_sec = float(parts[0])
                                end_sec = float(parts[1])
                            except:
                                # 尝试解析为时间格式 "MM:SS"
                                def parse_time(t: str) -> float:
                                    parts_time = t.split(":")
                                    if len(parts_time) == 2:
                                        return int(parts_time[0]) * 60 + int(parts_time[1])
                                    return 0.0
                                start_sec = parse_time(parts[0])
                                end_sec = parse_time(parts[1])
                    except:
                        pass
            
            # 如果还是没有，尝试从 duration 和 chunk_index 计算
            if start_sec is None or end_sec is None:
                duration = metadata.get("duration_seconds", 60)  # 默认60秒
                chunk_idx = metadata.get("chunk_index", 0)
                start_sec = chunk_idx * duration
                end_sec = start_sec + duration
            
            if start_sec is not None and end_sec is not None:
                # 提取摘要或使用文本前100字符
                summary = chunk.metadata.get("chunk_summary") or chunk.text[:100]
                if len(chunk.text) > 100:
                    summary += "..."
                
                timeline.append({
                    "start_sec": round(float(start_sec), 2),
                    "end_sec": round(float(end_sec), 2),
                    "summary": summary
                })
        
        # 按时间排序
        timeline.sort(key=lambda x: x["start_sec"])
        
        return timeline


def main():
    """命令行测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="视频理解引擎测试")
    parser.add_argument("--path", required=True, help="视频文件路径")
    
    args = parser.parse_args()
    
    engine = VideoEngine()
    
    try:
        print(f"提交视频: {args.path}")
        job_id = engine.submit_video(args.path)
        print(f"Job ID: {job_id}")
        
        # 等待处理完成
        print("处理中...")
        while True:
            status = engine.get_status(job_id)
            print(f"状态: {status['status']}, 进度: {status['progress']:.2%}")
            
            if status["status"] in ["succeeded", "failed"]:
                break
            
            time.sleep(1)
        
        if status["status"] == "succeeded":
            result = engine.get_result(job_id)
            print("\n结果:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            job = engine.store.get_job(job_id)
            print(f"处理失败: {job.get('error')}")
    
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

