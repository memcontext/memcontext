"""Placeholder video converter implementation."""

from __future__ import annotations

from typing import Any, List

from ..converter import ConversionChunk, ConversionOutput, MultimodalConverter
from ..factory import ConverterFactory


class VideoConverter(MultimodalConverter):
    SUPPORTED_EXTENSIONS: List[str] = ["mp4", "mov", "avi", "mkv", "webm", "flv"]

    def convert(self, source, *, source_type: str = "file_path", **kwargs: Any) -> ConversionOutput:
        """
        示例实现：不进行真实视频理解，仅返回固定文本，演示调用流程。
        """
        self._report_progress(0.3, "Simulating video-to-text conversion")
        chunk_metadata = {
            "source_type": "video",
            "chunk_index": 0,
            "chunk_count_estimate": 3,
            "duration_seconds": 45,
            "time_range": "00:00-00:30",
            "scene_label": "beach_feeding_gulls",
            "objects_detected": ["woman", "seagull", "ocean", "mountain"],
            "confidence": 0.92,
            "chunk_summary": "女子在沙滩喂海鸥，背景为海浪与山脉。",
            "language": "zh",
            "transcription_model": "demo_video_converter",
            "notes": "示例输出，无真实识别",
        }
        chunk = ConversionChunk(
            text="视频中，一位身着黄色连衣裙的女子背对着镜头，站在海边的沙滩上。她的头发自然垂落，发梢微卷，左手腕佩戴着一块白色表盘的手表。女子的右手高举，手中似乎握着食物，吸引着空中的海鸥。\n\n背景中，蓝色的海洋泛起层层白色浪花，远处矗立着一座轮廓清晰的山脉，天空晴朗湛蓝，营造出一种宁静而开阔的氛围。\n\n起初，一只海鸥从左侧飞向女子的手，随后更多的海鸥从不同方向（左侧、右侧及下方）飞至，它们在空中盘旋、俯冲，似乎在争抢食物。女子的手臂保持着固定姿势，目光专注地注视着海鸥。随着时间推移，海鸥的数量逐渐增多，有的海鸥已经靠近她的手，仿佛已经成功获取食物，而更多的海鸥则继续从远处飞来，动作活跃而充满生机。\n\n整个场景充满了自然的活力，海鸥的动态与女子的静态形成鲜明对比，背景的海景与山脉为画面增添了一份宁静与辽阔，整体氛围悠闲自在，仿佛在描绘一个人与自然和谐互动的美好瞬间。",
            chunk_index=chunk_metadata["chunk_index"],
            metadata=chunk_metadata,
        )
        self._report_progress(1.0, "Video conversion simulation completed")
        return ConversionOutput(
            status="success",
            chunks=[chunk],
            metadata={
                "converter_provider": "demo_video_converter",
                "converter_version": "0.1.0",
                "conversion_time": "2025-11-26T16:35:12Z",
                "notes": "示例文件级 metadata，真实实现可根据需要填充哈希等信息",
            },
        )

    def supports(self, *, file_type: str, mime_type: str = None) -> bool:
        return file_type.lower() in self.SUPPORTED_EXTENSIONS


# Register the placeholder converter as default
ConverterFactory.register("video", VideoConverter, priority=0)

