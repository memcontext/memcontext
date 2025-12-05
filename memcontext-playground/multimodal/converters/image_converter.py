"""Real image converter implementation using Volcengine SDK for image analysis."""
from __future__ import annotations
import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
try:
    from volcenginesdkarkruntime import Ark
except ImportError:
    Ark = None
# 处理相对导入，支持直接运行脚本
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from multimodal.converter import ConversionChunk, ConversionOutput, MultimodalConverter
from multimodal.factory import ConverterFactory
def load_env_file(env_path: Optional[Path] = None) -> None:
    """
    加载 .env 文件到环境变量
    如果 env_path 为 None，会在当前文件目录和父目录中查找 .env 文件
    """
    if env_path is None:
        current_file_dir = Path(__file__).parent
        env_path = current_file_dir / ".env"
        if not env_path.exists():
            parent_dir = current_file_dir.parent.parent
            env_path = parent_dir / ".env"
    if env_path and env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                loaded_count = 0
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    # 解析 KEY=VALUE 格式
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        # 设置环境变量（如果不存在则设置，避免覆盖已存在的环境变量）
                        if key and key not in os.environ:
                            os.environ[key] = value
                            loaded_count += 1
                if loaded_count > 0:
                    print(f"[INFO] 从 {env_path} 加载了 {loaded_count} 个环境变量")
        except Exception as e:
            print(f"[WARNING] 读取 .env 文件失败: {e}")
    else:
        if env_path:
            print(f"[DEBUG] 未找到 .env 文件，查找路径: {env_path}")

# 在模块加载时尝试加载 .env 文件
load_env_file()
class ImageConverter(MultimodalConverter):
    SUPPORTED_EXTENSIONS: List[str] = ["png", "jpg", "jpeg", "gif", "bmp", "webp"]
    def __init__(
        self,
        *,
        max_chunk_tokens: int = 4000,
        progress_callback: Optional[Any] = None,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        **config: Any,
    ) -> None:
        super().__init__(
            max_chunk_tokens=max_chunk_tokens,
            progress_callback=progress_callback,
            retry_count=retry_count,
            retry_delay=retry_delay,
            **config,
        )
        # 从 config 或环境变量获取配置
        self.api_key = api_key or config.get("api_key") or os.environ.get("LLM_API_KEY")
        self.base_url = base_url or config.get("base_url") or os.environ.get("LLM_BASE_URL")
        self.model = model or config.get("model") or os.environ.get("LLM_MODEL")
        # 初始化 Volcengine SDK 客户端
        if Ark is None:
            raise ImportError(
                "volcenginesdkarkruntime 未安装。请运行: pip install 'volcengine-python-sdk[ark]'"
            )
        if not self.api_key:
            raise ValueError("API key 必须配置。可通过 config 参数或环境变量 LLM_API_KEY 设置。")
        self.client = Ark(
            base_url=self.base_url,
            api_key=self.api_key,
        )
    def _encode_image(self, image_path: str) -> str:
        """
        将图片文件编码为 Base64 字符串
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    def _get_image_format(self, image_path: str) -> str:
        """
        从文件扩展名获取图片格式
        """
        ext = Path(image_path).suffix.lower().lstrip('.')
        # 映射常见扩展名到 MIME 类型
        format_map = {
            'png': 'png',
            'jpg': 'jpeg',
            'jpeg': 'jpeg',
            'gif': 'gif',
            'bmp': 'bmp',
            'webp': 'webp',
        }
        return format_map.get(ext, 'jpeg')

    def _analyze_image(self, image_path: str, prompt: str = "请详细描述这张图片的内容。") -> str:
        """
        分析本地图片文件并返回描述
        使用 Volcengine SDK 和 Base64 编码
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 将图片编码为 Base64
        self._report_progress(0.3, "正在编码图片文件...")
        base64_image = self._encode_image(image_path)
        image_format = self._get_image_format(image_path)
        # 使用 SDK 调用 API
        self._report_progress(0.5, f"正在分析图片: {os.path.basename(image_path)}...")
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )
        
        # 提取图片描述
        if completion.choices and len(completion.choices) > 0:
            image_description = completion.choices[0].message.content
            return image_description
        else:
            raise ValueError("无法从 API 响应中提取图片描述")

    def convert(self, source, *, source_type: str = "file_path", **kwargs: Any) -> ConversionOutput:
        """
        真实图片识别实现：使用 API 进行本地图片文件分析
        """
        try:
            # 只支持本地文件路径
            if source_type != "file_path":
                raise ValueError(f"ImageConverter 只支持本地文件路径 (source_type='file_path')，当前为: {source_type}")
            
            image_path = str(source)
            
            # 验证文件是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 分析图片
            self._report_progress(0.1, "开始分析图片内容...")
            prompt = kwargs.get("prompt", "请详细描述这张图片的内容，包括场景、人物、物体、颜色、位置等所有可见的视觉元素。")
            image_description = self._analyze_image(image_path, prompt)
            
            # 创建 chunk，保持原始的 chunk_metadata 格式
            chunk_metadata = {
                "source_type": "image",
                "chunk_index": 0,
                "chunk_count_estimate": 1,
            }
            
            chunk = ConversionChunk(
                text=image_description,
                chunk_index=0,
                metadata=chunk_metadata,
            )
            
            self._report_progress(1.0, "图片分析完成")
            
            return ConversionOutput(
                status="success",
                chunks=[chunk],
                metadata={
                    "converter_provider": "image_api_converter",
                    "converter_version": "1.0.0",
                    "conversion_time": datetime.utcnow().isoformat() + "Z",
                    "model": self.model,
                },
            )
        except Exception as e:
            return ConversionOutput(
                status="failed",
                chunks=[],
                metadata={
                    "converter_provider": "image_api_converter",
                    "converter_version": "1.0.0",
                },
                error=str(e),
            )

    def supports(self, *, file_type: str, mime_type: str = None) -> bool:
        return file_type.lower() in self.SUPPORTED_EXTENSIONS


# Register the converter
ConverterFactory.register("image", ImageConverter, priority=0)


def main():
    """测试 ImageConverter 功能"""
    import sys
    
    # 再次尝试加载 .env 文件（确保能找到）
    load_env_file()
    
    # 显示当前环境变量状态（用于调试）
    print("当前环境变量状态:")
    print(f"  LLM_API_KEY: {'已设置' if os.environ.get('LLM_API_KEY') else '未设置'}")
    print(f"  LLM_BASE_URL: {os.environ.get('LLM_BASE_URL', '未设置')}")
    print(f"  LLM_MODEL: {os.environ.get('LLM_MODEL', '未设置')}")
    print()
    
    # 检查是否提供了图片文件路径
    if len(sys.argv) < 2:
        print("用法: python image_converter.py <图片文件路径> [prompt]")
        print("示例: python image_converter.py test_image.jpg")
        print("示例: python image_converter.py test_image.jpg '图里有什么'")
        sys.exit(1)
    
    image_path = sys.argv[1]
    custom_prompt = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"错误: 图片文件不存在: {image_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("ImageConverter 测试")
    print("=" * 60)
    print(f"图片文件: {image_path}")
    if custom_prompt:
        print(f"自定义 Prompt: {custom_prompt}")
    print()
    
    # 进度回调函数
    def progress_callback(progress: float, message: str):
        print(f"[进度 {progress*100:.1f}%] {message}")
    
    try:
        # 创建转换器实例
        converter = ImageConverter(
            api_key=os.environ.get("LLM_API_KEY"),
            base_url=os.environ.get("LLM_BASE_URL"),
            model=os.environ.get("LLM_MODEL"),
            progress_callback=progress_callback,
        )
        
        print("开始转换图片...")
        print()
        
        # 执行转换
        kwargs = {}
        if custom_prompt:
            kwargs["prompt"] = custom_prompt
        
        result = converter.convert(image_path, source_type="file_path", **kwargs)
        
        print()
        print("=" * 60)
        print("转换结果")
        print("=" * 60)
        print(f"状态: {result.status}")
        
        if result.status == "success":
            print(f"Chunk 数量: {len(result.chunks)}")
            print()
            
            for i, chunk in enumerate(result.chunks):
                print(f"--- Chunk {i+1} ---")
                print(f"文本长度: {len(chunk.text)} 字符")
                print(f"元数据: {chunk.metadata}")
                print()
                print("图片描述内容:")
                print("-" * 60)
                print(chunk.text)
                print("-" * 60)
                print()
            
            print("输出元数据:")
            print(result.metadata)
        else:
            print(f"错误: {result.error}")
            if result.error:
                print(f"错误详情: {result.error}")
        
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请安装依赖: pip install 'volcengine-python-sdk[ark]'")
        sys.exit(1)
    except ValueError as e:
        print(f"配置错误: {e}")
        print("请设置环境变量 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL")
        print("或创建 .env 文件并配置这些变量")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
