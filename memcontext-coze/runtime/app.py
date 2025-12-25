"""
Coze 视频理解端插件主程序
使用 cozepy SDK 连接到扣子平台，处理端插件调用
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import List

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    # 从当前目录和父目录查找 .env 文件
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)  # override=False: 不覆盖已存在的环境变量
    else:
        # 尝试从项目根目录查找
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    # 如果没有安装 python-dotenv，跳过
    pass

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from cozepy import (
        COZE_CN_BASE_URL,
        COZE_COM_BASE_URL,
        ChatEvent,
        ChatEventType,
        Coze,
        Message,
        Stream,
        TokenAuth,
        ToolOutput,
    )
except ImportError as e:
    print(f"Error: cozepy not installed. Please run: pip install cozepy. Error: {e}")
    sys.exit(1)

from video_engine import VideoEngine


class LocalPlugin:
    """本地插件处理器"""
    
    def __init__(self, coze: Coze, engine: VideoEngine):
        self.coze = coze
        self.engine = engine
    
    def video_submit(self, tool_call_id: str, arguments: str) -> ToolOutput:
        """处理 video_submit"""
        args = json.loads(arguments)
        path = args.get("path")
        if not path:
            print(f"[提交失败] path 参数缺失", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": "path is required", "code": "MISSING_PARAMETER"}})
            )
        
        print(f"[提交视频] path: {path}", file=sys.stderr, flush=True)
        options = args.get("options", {})
        try:
            job_id = self.engine.submit_video(path, options)
            print(f"[任务ID] {job_id}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"job_id": job_id})
            )
        except ValueError as e:
            print(f"[提交失败] path: {path}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "INVALID_INPUT"}})
            )
        except Exception as e:
            print(f"[提交异常] path: {path}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "INTERNAL_ERROR"}})
            )
    
    def video_status(self, tool_call_id: str, arguments: str) -> ToolOutput:
        """处理 video_status"""
        args = json.loads(arguments)
        job_id = args.get("job_id")
        if not job_id:
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": "job_id is required", "code": "MISSING_PARAMETER"}})
            )
        
        print(f"[查询状态] job_id: {job_id}", file=sys.stderr, flush=True)
        try:
            status = self.engine.get_status(job_id)
            print(f"[状态结果] job_id: {job_id}, status: {status.get('status')}, progress: {status.get('progress')}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps(status)
            )
        except ValueError as e:
            print(f"[状态查询失败] job_id: {job_id}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "NOT_FOUND"}})
            )
        except Exception as e:
            print(f"[状态查询异常] job_id: {job_id}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "INTERNAL_ERROR"}})
            )
    
    def video_result(self, tool_call_id: str, arguments: str) -> ToolOutput:
        """处理 video_result"""
        args = json.loads(arguments)
        job_id = args.get("job_id")
        if not job_id:
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": "job_id is required", "code": "MISSING_PARAMETER"}})
            )
        
        print(f"[获取结果] job_id: {job_id}", file=sys.stderr, flush=True)
        try:
            result = self.engine.get_result(job_id)
            print(f"[结果成功] job_id: {job_id}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps(result, ensure_ascii=False)
            )
        except ValueError as e:
            print(f"[结果查询失败] job_id: {job_id}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "NOT_FOUND"}})
            )
        except Exception as e:
            print(f"[结果查询异常] job_id: {job_id}, error: {e}", file=sys.stderr, flush=True)
            return ToolOutput(
                tool_call_id=tool_call_id,
                output=json.dumps({"error": {"message": str(e), "code": "INTERNAL_ERROR"}})
            )


def handle_local_plugin(coze: Coze, engine: VideoEngine, event: ChatEvent):
    """处理端插件调用"""
    required_action = event.chat.required_action
    tool_calls = required_action.submit_tool_outputs.tool_calls
    
    local_plugin = LocalPlugin(coze, engine)
    tool_outputs: List[ToolOutput] = []
    
    # 处理所有 tool_calls
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        
        # 根据 function_name 调用对应方法
        if hasattr(local_plugin, function_name):
            handler = getattr(local_plugin, function_name)
            try:
                output = handler(tool_call.id, tool_call.function.arguments)
                tool_outputs.append(output)
            except Exception as e:
                print(f"[错误] 执行 {function_name} 时发生异常: {e}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc(file=sys.stderr)
                tool_outputs.append(ToolOutput(
                    tool_call_id=tool_call.id,
                    output=json.dumps({"error": {"message": str(e), "code": "EXECUTION_ERROR"}})
                ))
        else:
            # 未知的工具
            print(f"[错误] 未知的工具: {function_name}", file=sys.stderr, flush=True)
            tool_outputs.append(ToolOutput(
                tool_call_id=tool_call.id,
                output=json.dumps({"error": {"message": f"Unknown function: {function_name}", "code": "UNKNOWN_FUNCTION"}})
            ))
    
    # 提取 job_id（用于异常时输出）
    job_ids = []
    for tool_output in tool_outputs:
        try:
            output_data = json.loads(tool_output.output)
            if "job_id" in output_data:
                job_ids.append(output_data["job_id"])
        except:
            pass
    
    # 提交工具输出，继续流式输出
    try:
        submit_stream = coze.chat.submit_tool_outputs(
            conversation_id=event.chat.conversation_id,
            chat_id=event.chat.id,
            tool_outputs=tool_outputs,
            stream=True,
        )
        handle_coze_stream(coze, engine, "/v3/chat/submit_tool_outputs", submit_stream)
    except Exception as e:
        # 捕获网络异常：本地任务已执行，但结果未返回给 Bot
        error_type = type(e).__name__
        error_msg = str(e)
        
        if job_ids:
            # 如果有 job_id，说明任务已成功创建，只是结果没返回给 Bot
            print(f"[注意] 网络连接异常，结果未返回给 Bot，但任务已在本地创建成功", file=sys.stderr, flush=True)
            print(f"[任务ID] {', '.join(job_ids)} - 可使用 video_status 或 video_result 查询结果", file=sys.stderr, flush=True)
        else:
            # 没有 job_id，可能是其他类型的工具调用
            if "Timeout" in error_type or "timeout" in error_msg.lower():
                print(f"[警告] 网络超时，工具执行结果未返回给 Bot", file=sys.stderr, flush=True)
            elif "peer closed" in error_msg.lower() or "incomplete" in error_msg.lower() or "ConnectionReset" in error_type:
                print(f"[警告] 连接中断，工具执行结果未返回给 Bot", file=sys.stderr, flush=True)
            else:
                print(f"[警告] 提交工具输出时发生异常: {error_type}: {error_msg}", file=sys.stderr, flush=True)


def handle_coze_stream(coze: Coze, engine: VideoEngine, api: str, stream: Stream[ChatEvent]):
    """处理 SSE 事件流"""
    is_first_pkg = True
    for event in stream:
        if is_first_pkg:
            print(f"[{api}] logid: {event.response.logid}")
        
        # 模型输出事件
        if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
            print(event.message.content, end="", flush=True)
        
        # 端插件中断事件
        if event.event == ChatEventType.CONVERSATION_CHAT_REQUIRES_ACTION:
            handle_local_plugin(coze, engine, event)
        
        is_first_pkg = False


def run_local_plugin_app(coze: Coze, engine: VideoEngine, bot_id: str, user_id: str, user_input: str):
    """运行端插件应用"""
    # 使用 .chat.stream 发起流式对话
    stream = coze.chat.stream(
        bot_id=bot_id,
        user_id=user_id,
        additional_messages=[Message.build_user_question_text(user_input)]
    )
    # 处理 SSE 事件流
    handle_coze_stream(coze, engine, "/v3/chat", stream)


def main():
    parser = argparse.ArgumentParser(description="Coze 视频理解端插件")
    parser.add_argument(
        "--region",
        choices=["cn", "global"],
        default="cn",
        help="区域选择: cn (国内版) 或 global (海外版)"
    )
    
    args = parser.parse_args()
    
    # 读取环境变量
    token = os.environ.get("COZE_API_TOKEN")
    bot_id = os.environ.get("COZE_BOT_ID")
    
    if not token:
        print("Error: COZE_API_TOKEN environment variable is required")
        sys.exit(1)
    
    if not bot_id:
        print("Error: COZE_BOT_ID environment variable is required")
        sys.exit(1)
    
    # 设置 base_url
    if args.region == "cn":
        api_base = COZE_CN_BASE_URL
    else:
        api_base = COZE_COM_BASE_URL
    
    print(f"区域: {args.region}")
    print(f"Base URL: {api_base}")
    print(f"Bot ID: {bot_id}\n")
    
    # 初始化 Coze 客户端
    coze = Coze(auth=TokenAuth(token), base_url=api_base)
    
    # 初始化视频引擎
    engine = VideoEngine()
    
    # 交互式对话
    print("视频理解端插件已启动")
    print("输入 'exit' 或 'quit' 退出\n")
    
    import secrets
    user_id = secrets.token_urlsafe()
    
    while True:
        try:
            user_input = input("\n-----\n请输入你的问题：").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                break
            
            run_local_plugin_app(coze, engine, bot_id, user_id, user_input)
        
        except KeyboardInterrupt:
            print("\n\n退出")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
