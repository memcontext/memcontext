from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
import secrets
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import asyncio
from starlette.background import BackgroundTasks
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
# 加载 .env 文件中的环境变量
# load_dotenv 会自动从当前目录和父目录向上查找 .env 文件
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# 加载配置文件（用于负载均衡配置）
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
if not os.path.exists(config_path):
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')

GLOBAL_CONFIG = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            GLOBAL_CONFIG = json.load(f)
            print(f"Loaded configuration from {config_path}")
    except Exception as e:
        print(f"Error loading config.json: {e}")




executor = ThreadPoolExecutor(max_workers=10)

#  Memcontext
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from memcontext import Memcontext
from memcontext.utils import get_timestamp
from memcontext.storage import SupabaseStore
# 导入限流配置
from rate_limit_config import config as rate_limit_config

# Add parent directory to path to import memcontext
# Ensure the path is /root/autodl-tmp for consistent imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import memcontext modules directly
from memcontext import Memcontext
# Import utils directly from the playground directory
from memcontext.utils import get_timestamp

# Pydantic models for request validation
class InitMemoryRequest(BaseModel):
    user_id: str
    file_storage_base_path: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class ChatRequest(BaseModel):
    message: str

class ImportFromCacheRequest(BaseModel):
    file_id: str

class AddMultimodalMemoryRequest(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None
    converter_type: Optional[str] = None
    agent_response: Optional[str] = None
    converter_kwargs: Optional[Dict[str, Any]] = {}

class ConversationItem(BaseModel):
    user_input: str
    agent_response: str
    timestamp: Optional[str] = None

class ImportConversationsRequest(BaseModel):
    conversations: List[ConversationItem]


# ========================
# 1. 创建 Limiter 实例（从配置文件读取 Redis URI）
# ========================
# 注意：从 rate_limit_config 模块导入配置，便于集中管理
limiter = Limiter(
    key_func=get_remote_address,  # 限流键：按 IP 地址
    storage_uri=rate_limit_config.REDIS_URL  # 从配置文件读取 Redis URL
)


# Initialize FastAPI app
app = FastAPI(title="Memcontext API", version="1.0.0")

# Add session middleware (similar to Flask's session)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(16))

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
# Initialize templates (if needed for HTML rendering)
# 获取模板目录的绝对路径（相对于当前文件所在目录）
template_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.exists(template_dir):
    templates = Jinja2Templates(directory=template_dir)
else:
    templates = None

# Global memcontext instance (in production, you'd use proper session management)
memory_systems = {}

# ========================
# 限流辅助函数
# ========================
def get_rate_limit(route_path: str) -> str:
    """
    获取指定路由的限流规则
    
    Args:
        route_path: 路由路径，例如 '/chat'
        
    Returns:
        限流规则字符串，例如 '60/minute'
    """
    return rate_limit_config.get_route_limit(route_path)

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """首页路由 - 返回HTML模板"""
    # 注意：这里不需要 await，因为 render_template 是同步的
    # 但如果 templates 不存在，我们直接返回简单的HTML
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    else:
        return HTMLResponse(content="<html><body><h1>Memcontext API</h1></body></html>")

@app.post('/init_memory')
@limiter.limit(get_rate_limit('/init_memory'))
async def init_memory(data: InitMemoryRequest, request: Request):
    """
    初始化记忆系统
    注意：这里使用 async def，但内部调用的都是同步方法，所以不需要 await
    使用 async def 是为了保持 FastAPI 的一致性，如果将来需要异步操作可以方便扩展
    """
    user_id = data.user_id.strip() if data.user_id else ''
    if not user_id:
        raise HTTPException(status_code=400, detail='User ID 是必需的。')
    # 优先从配置文件读取，如果没有则从环境变量读取
    assistant_id = GLOBAL_CONFIG.get("assistant_id") or f"assistant_{user_id}"
    api_key = GLOBAL_CONFIG.get("openai_api_key", "")
    base_url = GLOBAL_CONFIG.get("openai_base_url", "https://api.openai.com/v1")
    model = GLOBAL_CONFIG.get("llm_model", "gpt-4o-mini")
    data_path = GLOBAL_CONFIG.get("data_storage_path", "./data")
    
    embedding_api_key = GLOBAL_CONFIG.get("embedding_api_key", "")
    embedding_base_url = GLOBAL_CONFIG.get("embedding_base_url", "https://ark.cn-beijing.volces.com/api/v3")
    embedding_model = GLOBAL_CONFIG.get("embedding_model_name", "doubao-embedding-large-text-250515")
    api_urls_keys = GLOBAL_CONFIG.get("openai_api_urls_keys", {})
    # 读取负载均衡配置（多个 API key）
    

    # Supabase 配置
    supa_cfg = GLOBAL_CONFIG.get("supabase", {}) or {}
    supa_url = supa_cfg.get("url")
    supa_key = supa_cfg.get("service_key")
    supa_schema = supa_cfg.get("schema", "public")
    supa_sessions_table = supa_cfg.get("mid_sessions_table", "sessions")
    supa_pages_table = supa_cfg.get("mid_pages_table", "pages")
    ltm_user_profiles_table = supa_cfg.get("ltm_user_profiles_table", "long_term_user_profiles")
    ltm_user_knowledge_table = supa_cfg.get("ltm_user_knowledge_table", "long_term_user_knowledge")
    ltm_assistant_knowledge_table = supa_cfg.get("ltm_assistant_knowledge_table", "long_term_assistant_knowledge")

    supa_store = None
    if supa_url and supa_key:
        try:
            # 从 config 读取 Postgres 连接信息（用于自动建表）
            postgres_host = supa_cfg.get("postgres_host")
            postgres_port = supa_cfg.get("postgres_port", 5432)
            postgres_db = supa_cfg.get("postgres_db", "postgres")
            postgres_user = supa_cfg.get("postgres_user", "postgres")
            postgres_password = supa_cfg.get("postgres_password")
            postgres_connection_string = supa_cfg.get("postgres_connection_string")
            
            # embedding_dim 与当前中期记忆 embedding 模型维度保持一致
            supa_store = SupabaseStore(
                supabase_url=supa_url,
                supabase_key=supa_key,
                embedding_dim=2048,
                schema=supa_schema,
                mid_sessions_table=supa_sessions_table,
                mid_pages_table=supa_pages_table,
                ltm_user_profiles_table=ltm_user_profiles_table,
                ltm_user_knowledge_table=ltm_user_knowledge_table,
                ltm_assistant_knowledge_table=ltm_assistant_knowledge_table,
                auto_create_tables=True,
                postgres_connection_string=postgres_connection_string,
                postgres_host=postgres_host,
                postgres_port=postgres_port,
                postgres_db=postgres_db,
                postgres_user=postgres_user,
                postgres_password=postgres_password,
            )
            print(f"SupabaseStore initialized for mid-term memory: {supa_url}")
        except Exception as e:
            print(f"Warning: Failed to initialize SupabaseStore, fallback to local mid_term.json. Error: {e}")



    
    
    # 如果没有配置负载均衡，则检查单个 API key
    if not api_urls_keys and not api_key:
        raise HTTPException(status_code=400, detail='LLM_API_KEY 环境变量或配置文件未配置，请设置豆包 API Key。')
    
    assistant_id = GLOBAL_CONFIG.get('assistant_id') or f"assistant_{user_id}"
    
    try:
        # Initialize memcontext for this session
        os.makedirs(data_path, exist_ok=True)
        
        # 获取 file_storage_base_path（可选，默认使用项目根目录）
        file_storage_base_path = data.file_storage_base_path.strip() if data.file_storage_base_path else ''
        if not file_storage_base_path:
            # 默认使用项目根目录，FileStorageManager 会在根目录下创建 files 目录
            # app_fastAPI.py 在 memdemo/ 目录下，所以上一级目录就是项目根目录
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            file_storage_base_path = project_root
        
        # 注意：Memcontext 初始化是同步操作，不需要 await
        memory_system = Memcontext(
            user_id=user_id,
            openai_api_key=api_key,
            openai_base_url=base_url,
            data_storage_path=data_path,
            assistant_id=assistant_id,
            short_term_capacity=GLOBAL_CONFIG.get('short_term_capacity', 7),
            mid_term_capacity=GLOBAL_CONFIG.get('mid_term_capacity', 200),
            long_term_knowledge_capacity=GLOBAL_CONFIG.get('long_term_knowledge_capacity', 1000),
            mid_term_heat_threshold=GLOBAL_CONFIG.get('mid_term_heat_threshold', 10.0),
            embedding_model_name=embedding_model,
            embedding_model_kwargs={'api_key': embedding_api_key, 'base_url': embedding_base_url},
            llm_model=model,
            file_storage_base_path=file_storage_base_path,
            openai_api_urls_keys=api_urls_keys if api_urls_keys else None,  # 传入负载均衡配置
            storage=supa_store,  # 使用 Supabase 存储（若已配置且表已建好）
        )
        
        session_id = secrets.token_hex(8)
        memory_systems[session_id] = memory_system
        # FastAPI 的 session 通过 request.session 访问
        request.session['memory_session_id'] = session_id
        # 将配置存入session（包括负载均衡配置）
        memory_config = {
            'api_key': api_key,
            'base_url': base_url,
            'model': model,
            'embedding_provider': 'doubao',
            'api_urls_keys': api_urls_keys,  # 保存负载均衡配置
            'embedding_api_key': embedding_api_key,
            'embedding_base_url': embedding_base_url,
            'embedding_model': embedding_model,
            'assistant_id': assistant_id,
            'data_path': data_path
        }
        request.session['memory_config'] = memory_config
        
        return {
            'success': True,
            'session_id': session_id,
            'user_id': user_id,
            'assistant_id': assistant_id,
            'model': model,
            'base_url': base_url,
            'embedding_provider': memory_config['embedding_provider']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/chat')
@limiter.limit(get_rate_limit('/chat'))
async def chat(data: ChatRequest, request: Request):
    """
    聊天接口
    注意：memory_system.get_response() 虽然是同步方法，但内部包含 LLM API 调用等阻塞操作
    使用 asyncio.to_thread() 在后台线程中运行，避免阻塞事件循环
    """
    user_input = data.message
    
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    
    try:
        # Get response from memcontext (this already adds the memory internally)
        # 注意：get_response() 内部包含同步的 LLM API 调用，会阻塞事件循环
        # 使用 asyncio.to_thread() 在后台线程中运行，避免阻塞
        response = await asyncio.to_thread(memory_system.get_response, user_input)
        
        # Do NOT add memory again here - it's already done in get_response()
        
        return {
            'response': response,
            'timestamp': get_timestamp()
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Chat error: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail={
                'error': str(e),
                'traceback': error_trace
            }
        )

@app.post('/import_from_cache')
@limiter.limit(get_rate_limit('/import_from_cache'))
async def import_from_cache_endpoint(data: ImportFromCacheRequest, request: Request):
    """
    从 temp_memory 缓存直接导入，跳过 videorag 解析
    注意：文件读取和 memory_system.add_memory() 都是同步操作，不需要 await
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')

    memory_system = memory_systems[session_id]
    
    try:
        file_id = data.file_id.strip() if data.file_id else ''
        
        if not file_id:
            raise HTTPException(status_code=400, detail='file_id is required')
        
        # 检查缓存文件
        cache_dir = Path(memory_system.data_storage_path) / "temp_memory"
        cache_file = cache_dir / f"{file_id}.json"
        
        if not cache_file.exists():
            raise HTTPException(status_code=404, detail=f'Cache file not found for file_id: {file_id}')
        
        # 加载缓存
        # 注意：文件 I/O 操作是同步的，不需要 await
        # 如果文件很大，可以考虑使用 aiofiles 库进行异步文件操作
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        
        # 构建 ConversionOutput
        from memcontext.multimodal.converter import ConversionChunk, ConversionOutput
        
        cached_chunks = []
        for idx, ch in enumerate(cached.get("chunks", [])):
            meta = ch.get("metadata", {}) or {}
            chunk_idx = meta.get("chunk_index", idx)
            cached_chunks.append(
                ConversionChunk(
                    text=ch.get("text", ""),
                    chunk_index=chunk_idx,
                    metadata=meta,
                )
            )
        
        output = ConversionOutput(
            status="success",
            text="\n\n".join(c.text for c in cached_chunks),
            chunks=cached_chunks,
            metadata=cached.get("metadata", {}),
        )
        output.ensure_chunks()
        
        # 直接使用 _ingest_single_multimodal 的逻辑来添加记忆
        base_metadata = cached.get("metadata", {})
        timestamps = []
        memories_to_add = []
        
        for chunk in output.chunks:
            # 安全地合并元数据，确保所有值都是字典
            try:
                base_meta = base_metadata if isinstance(base_metadata, dict) else {}
                chunk_meta_dict = chunk.metadata if isinstance(chunk.metadata, dict) else {}
                
                chunk_meta = {
                    **base_meta,
                    **chunk_meta_dict,
                    "source_type": "multimodal",
                }
            except (TypeError, AttributeError) as e:
                print(f"Import cache: Error merging metadata: {e}")
                chunk_meta = {"source_type": "multimodal"}
            
            # 对于视频内容，使用完整的文本描述（chunk.text）作为 agent_response
            # 这样检索时能获得详细的视频内容，而不是只有摘要
            if chunk_meta.get("video_path") or chunk_meta.get("video_name"):
                chunk_agent_response = chunk.text  # 使用完整的视频描述文本
            else:
                chunk_agent_response = chunk_meta.get(
                    "chunk_summary",
                    f"[Multimodal] Stored content from {chunk_meta.get('original_filename', 'file')}",
                )
            
            # 对于视频内容，构建格式化的 user_input
            # 安全获取 video_path，确保不会为 None 或抛出 KeyError
            try:
                video_path = chunk_meta.get("video_path") or chunk_meta.get("original_filename") or chunk_meta.get("video_name") or "视频"
                time_range = chunk_meta.get("time_range", "")
                
                if (chunk_meta.get("video_path") or chunk_meta.get("video_name")) and time_range:
                    # 确保 video_path 是字符串且不为空
                    if not isinstance(video_path, str) or not video_path or video_path == "视频":
                        video_path = chunk_meta.get("video_name") or chunk_meta.get("original_filename") or "视频"
                    if not isinstance(video_path, str):
                        video_path = str(video_path) if video_path else "视频"
                    user_input = f"描述{video_path}视频的{time_range}的内容"
                else:
                    user_input = chunk.text
            except Exception as e:
                print(f"Import cache: Error building user_input: {e}, using chunk.text as fallback")
                user_input = chunk.text
                video_path = "视频"  # 设置默认值
            
            memories_to_add.append({
                "user_input": user_input,
                "agent_response": chunk_agent_response,
                "timestamp": get_timestamp(),
                "meta_data": chunk_meta,
            })
            timestamps.append(get_timestamp())
        
        # 使用正常流程：逐个添加到 short_term
        # 注意：add_memory() 虽然是同步方法，但可能触发中期记忆分析（包含 LLM 调用）
        # 使用 asyncio.to_thread() 在后台线程中运行，避免阻塞事件循环
        for mem in memories_to_add:
            await asyncio.to_thread(
                memory_system.add_memory,
                user_input=mem["user_input"],
                agent_response=mem["agent_response"],
                timestamp=mem["timestamp"],
                meta_data=mem["meta_data"]
            )
        
        return {
            'success': True,
            'ingested_rounds': len(memories_to_add),
            'file_id': file_id,
            'timestamps': timestamps,
            'message': f'Successfully imported {len(memories_to_add)} chunks from cache'
        }
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                'error': f'导入缓存失败: {str(e)}',
                'traceback': traceback.format_exc()
            }
        )

@app.post('/add_multimodal_memory_stream')
@limiter.limit(get_rate_limit('/add_multimodal_memory_stream'))
async def add_multimodal_memory_stream(request: Request):
    """
    流式返回视频处理进度的端点
    注意：这里使用异步生成器来支持 Server-Sent Events (SSE)
    虽然 add_multimodal_memory() 是同步的，但我们在后台线程中运行它
    使用 asyncio.to_thread() 或 run_in_executor() 来避免阻塞事件循环
    """
    import queue
    import threading
    
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        async def error_gen():
            yield f"data: {json.dumps({'error': 'Memory system not initialized'})}\n\n"
        return StreamingResponse(error_gen(), media_type='text/event-stream')
    
    memory_system = memory_systems[session_id]
    # FastAPI 中获取 JSON 数据
    # 注意：request.json() 是异步方法，需要 await
    # 这是因为 FastAPI 需要从请求流中异步读取数据
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    file_path = data.get('file_path')
    converter_type = (data.get('converter_type') or 'video').lower()
    agent_response = data.get('agent_response')
    converter_kwargs = data.get('converter_kwargs', {})
    
    if not file_path:
        async def error_gen():
            yield f"data: {json.dumps({'error': 'file_path is required'})}\n\n"
        return StreamingResponse(error_gen(), media_type='text/event-stream')
    
    progress_queue = queue.Queue()
    
    def progress_callback(progress: float, message: str) -> None:
        progress_queue.put({'progress': round(float(progress), 4), 'message': message})
    
    result_holder = {'result': None, 'error': None}
    
    def process_video():
        """在后台线程中处理视频，避免阻塞事件循环"""
        try:
            converter_settings = dict(converter_kwargs or {})
            converter_settings.setdefault('working_dir', './videorag-workdir')
            # 注意：add_multimodal_memory() 是同步方法，在后台线程中运行
            result = memory_system.add_multimodal_memory(
                source=file_path,
                source_type='file_path',
                converter_type=converter_type,
                agent_response=agent_response,
                converter_kwargs=converter_settings,
                progress_callback=progress_callback,
            )
            result_holder['result'] = result
        except Exception as e:
            result_holder['error'] = str(e)
        finally:
            progress_queue.put(None)  # 信号结束
    
    async def generate():
        """
        异步生成器函数，用于流式响应
        注意：这里使用 asyncio.to_thread() 在后台线程中运行同步的视频处理函数
        这样可以避免阻塞 FastAPI 的事件循环
        """
        # 在后台线程中运行视频处理
        loop = asyncio.get_event_loop()
        thread = threading.Thread(target=process_video)
        thread.start()
        
        while True:
            try:
                # 使用 asyncio.sleep 来让出控制权，避免阻塞
                await asyncio.sleep(0.1)
                try:
                    item = progress_queue.get_nowait()
                    if item is None:
                        break
                    yield f"data: {json.dumps(item)}\n\n"
                except queue.Empty:
                    # 发送心跳保持连接
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
            except Exception as e:
                print(f"Stream error: {e}")
                break
        
        thread.join()
        
        if result_holder['error']:
            yield f"data: {json.dumps({'done': True, 'error': result_holder['error']})}\n\n"
        else:
            res = result_holder['result']
            yield f"data: {json.dumps({'done': True, 'success': True, 'chunks_written': res.get('chunks_written', 0), 'file_id': res.get('file_id')})}\n\n"
    
    return StreamingResponse(generate(), media_type='text/event-stream')


@app.post('/add_multimodal_memory')
@limiter.limit(get_rate_limit('/add_multimodal_memory'))
async def add_multimodal_memory_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    agent_response: Optional[str] = Form(None),
    converter_type: Optional[str] = Form(None),
    converter_kwargs: Optional[str] = Form(None)
):
    """
    添加多模态记忆（支持文件上传或 JSON）
    注意：
    1. 文件上传使用 UploadFile，需要 await file.read() 来读取文件内容
    2. add_multimodal_memory() 是同步方法，不需要 await
    3. 文件 I/O 操作是同步的，但 FastAPI 会自动在后台线程中处理
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')

    memory_system = memory_systems[session_id]
    cleanup_paths = []

    try:
        source = None
        source_type = None
        final_converter_type = None
        final_agent_response = None
        final_converter_kwargs = {}

        # 检查是否有文件上传
        if file and file.filename:
            # 处理文件上传
            safe_name = secure_filename(file.filename)
            temp_dir = tempfile.mkdtemp(prefix="memcontext_upload_")
            temp_path = os.path.join(temp_dir, safe_name or "upload.bin")
            
            # 注意：这里需要 await，因为 file.read() 是异步方法
            # 文件读取是 I/O 操作，使用异步可以避免阻塞事件循环
            content = await file.read()
            with open(temp_path, "wb") as f:
                f.write(content)
            cleanup_paths.append(temp_dir)

            source = temp_path
            source_type = 'file_path'
            final_agent_response = agent_response
            final_converter_type = converter_type
            if converter_kwargs:
                try:
                    final_converter_kwargs = json.loads(converter_kwargs)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail='converter_kwargs must be valid JSON')
        else:
            # 处理 JSON 请求
            # 注意：request.json() 是异步方法，需要 await
            # 这是因为 FastAPI 需要从请求流中异步读取数据
            data = await request.json() if request.headers.get('content-type') == 'application/json' else {}
            if data.get('file_path'):
                source = data['file_path']
                source_type = 'file_path'
            elif data.get('url'):
                source = data['url']
                source_type = 'url'
            else:
                raise HTTPException(status_code=400, detail='file_path or url must be provided')

            final_converter_type = data.get('converter_type')
            final_agent_response = data.get('agent_response')
            final_converter_kwargs = data.get('converter_kwargs', {})

        if source_type != 'file_path':
            raise HTTPException(status_code=400, detail='当前仅支持本地文件路径(file_path)的视频源')

        final_converter_type = (final_converter_type or 'videorag').lower()
        if final_converter_type not in ('video', 'videorag'):
            raise HTTPException(status_code=400, detail=f'不支持的 converter_type: {final_converter_type}，可选 video | videorag')

        converter_settings = dict(final_converter_kwargs or {})
        # 移除不再使用的 deepseek_key 和 siliconflow_key
        converter_settings.pop('deepseek_key', None)
        converter_settings.pop('siliconflow_key', None)

        converter_settings.setdefault('working_dir', './videorag-workdir')
        progress_events = []

        def progress_callback(progress: float, message: str) -> None:
            progress_events.append({
                'progress': round(float(progress), 4),
                'message': message
            })

        # 使用 memory_system.add_multimodal_memory() 方法，它会自动处理所有chunks并存储到记忆中
        # 注意：add_multimodal_memory() 虽然是同步方法，但包含视频处理、LLM 调用等耗时操作
        # 使用 asyncio.to_thread() 在后台线程中运行，避免阻塞事件循环
        try:
            result = await asyncio.to_thread(
                memory_system.add_multimodal_memory,
                source=source,
                source_type=source_type,
                converter_type=final_converter_type,
                agent_response=final_agent_response,
                converter_kwargs=converter_settings,
                progress_callback=progress_callback,
            )
            
            if result.get('status') != 'success':
                raise HTTPException(
                    status_code=500,
                    detail={
                        'error': result.get('error', '处理失败'),
                        'metadata': result,
                        'progress': progress_events
                    }
                )

            response_data = {
                'success': True,
                'ingested_rounds': result.get('chunks_written', 0),
                'file_id': result.get('file_id'),
                'timestamps': result.get('timestamps', []),
                'progress': progress_events
            }
            # 如果有存储路径信息，也返回
            if result.get('storage_path'):
                response_data['storage_path'] = result.get('storage_path')
            if result.get('storage_base_path'):
                response_data['storage_base_path'] = result.get('storage_base_path')
            return response_data
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    'error': f'调用 add_multimodal_memory 失败: {str(e)}',
                    'progress': progress_events
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in cleanup_paths:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

@app.get('/memory_state')
@limiter.limit(get_rate_limit('/memory_state'))
async def get_memory_state(request: Request):
    """
    获取记忆状态
    注意：所有 memory 相关的方法都是同步的，不需要 await
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    
    try:
        # Get short-term memory
        short_term = memory_system.short_term_memory.get_all()
        mid_term_sessions = []
        # Get mid-term memory sessions (top 5)
        for sid, session_data in list(memory_system.mid_term_memory.sessions.items())[:5]:
            mid_term_sessions.append({
                'id': sid,
                'summary': session_data.get('summary', ''),
                'keywords': session_data.get('summary_keywords', []),
                'heat': session_data.get('H_segment', 0),
                'visit_count': session_data.get('N_visit', 0),
                'last_visit': session_data.get('last_visit_time', ''),
                'page_count': len(session_data.get('details', []))
            })
        
        # Sort by heat
        mid_term_sessions.sort(key=lambda x: x['heat'], reverse=True)
        
        # Get long-term memory - separate user profile, user knowledge, and assistant knowledge
        user_profile = memory_system.user_long_term_memory.get_raw_user_profile(memory_system.user_id)
        user_knowledge = memory_system.user_long_term_memory.get_user_knowledge()
        assistant_knowledge = memory_system.assistant_long_term_memory.get_assistant_knowledge()
        return {
            'short_term': {
                'capacity': memory_system.short_term_memory.max_capacity,
                'current_count': len(short_term),
                'memories': short_term
            },
            'mid_term': {
                'capacity': memory_system.mid_term_memory.max_capacity,
                'current_count': len(memory_system.mid_term_memory.sessions),
                'sessions': mid_term_sessions,
                'heat_threshold': memory_system.mid_term_heat_threshold
            },
            'long_term': {
                'user_profile': user_profile,
                'user_knowledge': [k.get('knowledge', '') for k in user_knowledge],
                'assistant_knowledge': [k.get('knowledge', '') for k in assistant_knowledge]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/trigger_analysis')
@limiter.limit(get_rate_limit('/trigger_analysis'))
async def trigger_analysis(request: Request):
    """
    触发中期记忆分析
    注意：force_mid_term_analysis() 虽然是同步方法，但内部包含 LLM 调用等阻塞操作
    使用 asyncio.to_thread() 在后台线程中运行，避免阻塞事件循环
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    
    try:
        # Check if there are any mid-term memory sessions to analyze
        if not memory_system.mid_term_memory.sessions:
            raise HTTPException(status_code=400, detail='No Mid-term memory, but at least keep short-term memory for seven rounds.')
        
        # Check if there are any unanalyzed pages in mid-term memory
        has_unanalyzed_pages = False
        for session_data in memory_system.mid_term_memory.sessions.values():
            unanalyzed_pages = [p for p in session_data.get('details', []) if not p.get('analyzed', False)]
            if unanalyzed_pages:
                has_unanalyzed_pages = True
                break
        
        if not has_unanalyzed_pages:
            raise HTTPException(status_code=400, detail='No Mid-term memory, but at least keep short-term memory for seven rounds.')
        
        # Force mid-term analysis (内部包含 LLM 调用，使用后台线程运行)
        await asyncio.to_thread(memory_system.force_mid_term_analysis)
        return {'success': True, 'message': 'Analysis triggered successfully'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/personality_analysis')
@limiter.limit(get_rate_limit('/personality_analysis'))
async def personality_analysis(request: Request):
    """
    人格分析
    注意：所有方法都是同步的，不需要 await
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    
    try:
        # Get user profile
        user_profile = memory_system.user_long_term_memory.get_raw_user_profile(memory_system.user_id)
        
        if not user_profile or user_profile.lower() in ['none', 'no profile data yet']:
            raise HTTPException(status_code=400, detail='No user profile available for analysis')
        
        # Parse personality traits from the user profile
        personality_analysis_result = parse_personality_traits(user_profile)
        
        return {
            'success': True,
            'personality_analysis': personality_analysis_result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def parse_personality_traits(user_profile):
    """
    Parse personality traits from user profile text.
    Extract traits in format: Dimension ( Level(High/Medium/Low) )
    """
    # Define the three main categories
    categories = {
        'Psychological Model': [
            'Extraversion', 'Openness', 'Agreeableness', 'Conscientiousness', 'Neuroticism',
            'Physiological Needs', 'Need for Security', 'Need for Belonging', 'Need for Self-Esteem',
            'Cognitive Needs', 'Aesthetic Appreciation', 'Self-Actualization', 'Need for Order',
            'Need for Autonomy', 'Need for Power', 'Need for Achievement'
        ],
        'AI Alignment Dimensions': [
            'Helpfulness', 'Honesty', 'Safety', 'Instruction Compliance', 'Truthfulness',
            'Coherence', 'Complexity', 'Conciseness'
        ],
        'Content Platform Interest Tags': [
            'Science Interest', 'Education Interest', 'Psychology Interest', 'Family Concern',
            'Fashion Interest', 'Art Interest', 'Health Concern', 'Financial Management Interest',
            'Sports Interest', 'Food Interest', 'Travel Interest', 'Music Interest',
            'Literature Interest', 'Film Interest', 'Social Media Activity', 'Tech Interest',
            'Environmental Concern', 'History Interest', 'Political Concern', 'Religious Interest',
            'Gaming Interest', 'Animal Concern', 'Emotional Expression', 'Sense of Humor',
            'Information Density', 'Language Style', 'Practicality'
        ]
    }
    
    # Extract traits from user profile
    extracted_traits = {}
    
    import re
    
    # Look for patterns like "Dimension ( Level(High/Medium/Low) )"
    pattern = r'([A-Za-z\s]+)\s*\(\s*([A-Za-z]+)\s*\)'
    matches = re.findall(pattern, user_profile)
    
    for match in matches:
        dimension = match[0].strip()
        level = match[1].strip()
        
        # Find which category this dimension belongs to
        for category, dimensions in categories.items():
            for cat_dimension in dimensions:
                if dimension.lower() in cat_dimension.lower() or cat_dimension.lower() in dimension.lower():
                    if category not in extracted_traits:
                        extracted_traits[category] = []
                    extracted_traits[category].append({
                        'dimension': dimension,
                        'level': level
                    })
                    break
    
    # Alternative pattern: look for lines containing trait descriptions
    lines = user_profile.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for mentions of High/Medium/Low levels
        for level in ['High', 'Medium', 'Low']:
            if level.lower() in line.lower():
                # Try to extract the dimension name
                for category, dimensions in categories.items():
                    for dimension in dimensions:
                        if dimension.lower() in line.lower():
                            if category not in extracted_traits:
                                extracted_traits[category] = []
                            
                            # Check if this trait is already added
                            existing = [t for t in extracted_traits[category] if t['dimension'] == dimension]
                            if not existing:
                                extracted_traits[category].append({
                                    'dimension': dimension,
                                    'level': level
                                })
                            break
    
    return extracted_traits

@app.post('/clear_memory')
@limiter.limit(get_rate_limit('/clear_memory'))
async def clear_memory(request: Request):
    """
    清空记忆
    注意：文件删除操作是同步的，如果目录很大可能会阻塞事件循环
    使用 asyncio.to_thread() 在后台线程中运行，避免阻塞
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    
    try:
        # Clear all memory files
        user_data_dir = memory_system.user_data_dir
        assistant_data_dir = memory_system.assistant_data_dir
        
        # Remove the entire user data directory
        # 注意：shutil.rmtree() 是同步的，如果目录很大可能会阻塞事件循环
        # 使用 asyncio.to_thread() 在后台线程中运行
        if os.path.exists(user_data_dir):
            await asyncio.to_thread(shutil.rmtree, user_data_dir)
        
        # Remove the entire assistant data directory  
        if os.path.exists(assistant_data_dir):
            await asyncio.to_thread(shutil.rmtree, assistant_data_dir)
        
        # 从session中获取配置来重新初始化
        config = request.session.get('memory_config')
        if not config:
            raise HTTPException(status_code=400, detail='Configuration not found in session. Please re-initialize.')

        api_key = config.get('api_key', '')
        base_url = config.get('base_url', 'https://ark.cn-beijing.volces.com/api/v3')
        model = config.get('model', 'doubao-seed-1-6-flash-250828')
        api_urls_keys = config.get('api_urls_keys', {})  # 获取负载均衡配置
        embedding_api_key = config.get('embedding_api_key', api_key)
        embedding_base_url = config.get('embedding_base_url', base_url)
        embedding_model = config.get('embedding_model', 'doubao-embedding-large-text-250515')
        assistant_id = config.get('assistant_id', memory_system.assistant_id)
        data_path = config.get('data_path', memory_system.data_storage_path)
        
        user_id = memory_system.user_id
        
        # Create new memory system（支持负载均衡）
        new_memory_system = Memcontext(
            user_id=user_id,
            openai_api_key=api_key,
            openai_base_url=base_url,
            data_storage_path=data_path,
            assistant_id=assistant_id,
            short_term_capacity=GLOBAL_CONFIG.get('short_term_capacity', 7),
            mid_term_capacity=GLOBAL_CONFIG.get('mid_term_capacity', 200),
            long_term_knowledge_capacity=GLOBAL_CONFIG.get('long_term_knowledge_capacity', 100),
            mid_term_heat_threshold=GLOBAL_CONFIG.get('mid_term_heat_threshold', 5.0),
            llm_model=model,
            embedding_model_name=embedding_model,
            embedding_model_kwargs={'api_key': embedding_api_key, 'base_url': embedding_base_url},
            openai_api_urls_keys=api_urls_keys if api_urls_keys else None  # 传入负载均衡配置
        )
        
        # Replace the old memory system
        memory_systems[session_id] = new_memory_system
        
        return {'success': True, 'message': 'All memories cleared successfully'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/import_conversations')
@limiter.limit(get_rate_limit('/import_conversations'))
async def import_conversations(data: ImportConversationsRequest, request: Request):
    """
    导入对话历史
    注意：
    1. request.json() 需要 await（但这里使用 Pydantic 模型，自动处理）
    2. add_memory() 是同步方法，不需要 await
    """
    session_id = request.session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        raise HTTPException(status_code=400, detail='Memory system not initialized')
    
    memory_system = memory_systems[session_id]
    conversations = data.conversations
    
    if not conversations:
        raise HTTPException(status_code=400, detail='No conversations provided')
    
    try:
        imported_count = 0
        for conv in conversations:
            # 处理 Pydantic 模型或字典
            if isinstance(conv, dict):
                user_input = conv.get('user_input', '')
                agent_response = conv.get('agent_response', '')
                timestamp = conv.get('timestamp', get_timestamp())
            else:
                user_input = conv.user_input if hasattr(conv, 'user_input') else ''
                agent_response = conv.agent_response if hasattr(conv, 'agent_response') else ''
                timestamp = conv.timestamp if hasattr(conv, 'timestamp') and conv.timestamp else get_timestamp()
            
            if user_input and agent_response:
                # Add each conversation to memory system
                # 注意：add_memory() 虽然是同步方法，但可能触发中期记忆分析（包含 LLM 调用）
                # 使用 asyncio.to_thread() 在后台线程中运行，避免阻塞事件循环
                await asyncio.to_thread(
                    memory_system.add_memory,
                    user_input=user_input,
                    agent_response=agent_response,
                    timestamp=timestamp
                )
                imported_count += 1
            else:
                print(f"Skipping invalid conversation: {conv}")
        
        return {
            'success': True,
            'imported_count': imported_count,
            'message': f'Successfully imported {imported_count} conversations'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    # 使用 uvicorn 运行 FastAPI 应用
    # 
    # 运行方式（推荐）：
    # 1. 使用命令行（支持热重载）：
    #    uvicorn memdemo.app_fastAPI:app --reload --host 0.0.0.0 --port 5019
    # 
    # 2. 直接运行此文件（不支持热重载，但更简单）：
    #    python memdemo/app_fastAPI.py
    # 
    # 注意：如果直接运行文件时使用 reload=True，uvicorn 需要将应用作为导入字符串传递
    # 但直接运行文件时，Python 路径可能无法正确解析模块路径，所以这里不使用 reload
    uvicorn.run(
        app,  # 直接传递 app 对象
        host='0.0.0.0', 
        port=5019, 
        reload=False  # 直接运行时不支持 reload，如需热重载请使用命令行方式
    ) 