"""
文件存储管理模块使用示例
"""

import os
import sys
from pathlib import Path

# 支持直接运行和作为模块导入
try:
    from .storage_manager import FileStorageManager
    from .file_types import FileType
    from .api_server import create_api_server
except ImportError:
    # 直接运行时，添加父目录到路径
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from file_storage.storage_manager import FileStorageManager
    from file_storage.file_types import FileType
    from file_storage.api_server import create_api_server

# 导入 video 转换器用于视频切分
try:
    from multimodal.converters.video_converter import VideoConverter
except ImportError:
    VideoConverter = None


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 初始化存储管理器
    storage_path = "./test_storage"
    user_id = "test_user"
    manager = FileStorageManager(storage_path, user_id)
    
    # 上传文件（假设有一个测试视频文件）
    test_video_path = "D:\\project\\memcontext-memcontext\\memcontext-playground\\file_storage\\test3.mp4"  # 替换为实际文件路径
    
    if os.path.exists(test_video_path):
        # 上传文件
        file_record = manager.upload_file(test_video_path)
        print(f"文件上传成功: {file_record.file_id}")
        print(f"文件类型: {file_record.file_type.value}")
        print(f"存储路径: {file_record.stored_path}")
        print(f"元数据: {file_record.metadata}")
        
        # 获取文件路径
        file_path = manager.get_file_path(file_record.file_id)
        print(f"文件路径: {file_path}")
        
        # 使用 video 转换器按1分钟切分视频（如果文件是视频）
        if file_record.file_type == FileType.VIDEO and VideoConverter:
            print("\n使用 video 转换器按1分钟切分视频...")
            try:
                # 创建 video 转换器
                converter = VideoConverter()
                
                # 使用 video 转换器切分视频（按1分钟一段）
                video_path = file_path
                segments = converter._split_video_by_time(video_path, segment_duration=60)
                
                print(f"视频已切分成 {len(segments)} 个片段（按1分钟一段）:")
                
                # 获取 VideoHandler 来保存片段
                handler = manager.get_handler(FileType.VIDEO)
                from file_storage.utils import format_time_for_filename
                import shutil
                
                # 将切分后的片段复制到 file_storage 的 segments 目录
                saved_count = 0
                for i, (temp_segment_path, start_time, end_time) in enumerate(segments, 1):
                    duration = end_time - start_time
                    print(f"  片段 {i}: {start_time:.1f}s - {end_time:.1f}s (时长: {duration:.1f}秒)", end="")
                    
                    # 使用 VideoHandler 的方法来保存片段（会自动生成正确的文件名和路径）
                    try:
                        # 使用 get_segment_path 方法，它会自动处理路径和文件名
                        location_info = {
                            'start_time': start_time,
                            'end_time': end_time
                        }
                        target_segment_path = handler.get_segment_path(file_record.file_id, location_info)
                        
                        # 如果目标文件不存在，从临时文件复制
                        if not os.path.exists(target_segment_path):
                            # 确保目录存在
                            os.makedirs(os.path.dirname(target_segment_path), exist_ok=True)
                            shutil.copy2(temp_segment_path, target_segment_path)
                            saved_count += 1
                            print(" ✅ 已保存")
                        else:
                            print(" (已存在，跳过)")
                    except Exception as e:
                        print(f" ⚠️  保存失败: {e}")
                    
                    if duration < 60:
                        print(f"    ⚠️  最后一段不足1分钟，按实际时长 {duration:.1f}秒切分")
                
                print(f"\n✅ 视频切分完成，共 {len(segments)} 个片段，已保存 {saved_count} 个新片段到存储目录")
                
                # 列出所有已保存的片段
                saved_segments = handler.list_segments(file_record.file_id)
                if saved_segments:
                    print(f"\n已保存的片段列表（共 {len(saved_segments)} 个）:")
                    for seg in saved_segments:
                        print(f"  - {seg.start_time:.1f}s - {seg.end_time:.1f}s (时长: {seg.duration:.1f}秒)")
            except Exception as e:
                print(f"⚠️  视频切分失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 如果需要获取特定时间段的片段，可以使用以下代码：
        # if file_record.file_type == FileType.VIDEO:
        #     handler = manager.get_handler(FileType.VIDEO)
        #     segment_path = handler.get_segment_by_time(
        #         file_record.file_id,
        #         start_time=5.0,
        #         end_time=10.0
        #     )
    else:
        print(f"测试文件不存在: {test_video_path}")


def example_api_server():
    """API服务器使用示例"""
    print("\n=== API服务器示例 ===")
    
    storage_path = "./test_storage"
    user_id = "test_user"
    
    # 创建API服务器
    server = create_api_server(
        storage_base_path=storage_path,
        user_id=user_id,
        host="0.0.0.0",
        port=5001,
        debug=True
    )
    
    print("API服务器已创建")
    print("启动服务器请运行: server.run()")
    print("\n可用端点:")
    print("  POST /api/files/upload - 上传文件")
    print("  GET  /api/files/<file_id> - 获取文件")
    print("  GET  /api/files/<file_id>/segment?start_time=X&end_time=Y - 获取视频片段")
    print("  GET  /api/files/<file_id>/metadata - 获取文件元数据")
    print("  GET  /api/files - 列出所有文件")
    print("  DELETE /api/files/<file_id> - 删除文件")


def example_file_management():
    """文件管理示例"""
    print("\n=== 文件管理示例 ===")
    
    storage_path = "./test_storage"
    user_id = "test_user"
    manager = FileStorageManager(storage_path, user_id)
    
    # 列出所有文件
    all_files = manager.list_files()
    print(f"所有文件数: {len(all_files)}")
    
    # 列出特定类型的文件
    video_files = manager.list_files(FileType.VIDEO)
    print(f"视频文件数: {len(video_files)}")
    
    # 获取文件元数据
    if all_files:
        file_id = all_files[0].file_id
        metadata = manager.get_file_metadata(file_id)
        print(f"文件 {file_id} 的元数据: {metadata}")


if __name__ == '__main__':
    print("文件存储管理模块使用示例\n")
    
    # 运行示例
    example_basic_usage()
    example_file_management()
    example_api_server()
    
    print("\n示例完成！")
