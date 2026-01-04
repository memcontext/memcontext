from flask import Flask, request, jsonify
from functools import wraps
import os
import sys
import json
import shutil
import tempfile
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# 导入 memcontext
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from memcontext import Memcontext
from memcontext.utils import get_timestamp

app = Flask(__name__)

# 配置 Flask JSON 编码器，不转义中文字符
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json;charset=utf-8'

# 按 user_id 管理的记忆系统
memory_systems = {}         # {user_id: Memcontext}
user_memory_configs = {}    # {user_id: config}


# 统一响应（RestResult）
def make_response(code=200, message="操作成功", error_code=0, data=None):
    return jsonify({
        "code": code,
        "message": message,
        "errorCode": error_code,
        "data": data
    }), code


# 获取/创建记忆系统（基于 user_id）
def get_or_create_memory_system(user_id: str):
    if not user_id or not user_id.strip():
        raise ValueError("user_id 不能为空")
    user_id = user_id.strip()

    if user_id in memory_systems:
        return memory_systems[user_id]

    api_key = os.environ.get('LLM_API_KEY', '').strip()
    base_url = os.environ.get('LLM_BASE_URL', '').strip()
    model = os.environ.get('LLM_MODEL', '').strip()
    embedding_model = os.environ.get('EMBEDDING_MODEL', '').strip()

    if not api_key:
        raise ValueError("LLM_API_KEY 环境变量未配置，请设置 API Key")

    data_path = './data'
    os.makedirs(data_path, exist_ok=True)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    file_storage_base_path = project_root

    assistant_id = f"assistant_{user_id}"
    memory_system = Memcontext(
        user_id=user_id,
        openai_api_key=api_key,
        openai_base_url=base_url,
        data_storage_path=data_path,
        assistant_id=assistant_id,
        short_term_capacity=7,
        mid_term_capacity=200,
        long_term_knowledge_capacity=1000,
        mid_term_heat_threshold=10.0,
        embedding_model_name=embedding_model,
        embedding_model_kwargs={},
        llm_model=model,
        file_storage_base_path=file_storage_base_path
    )

    memory_systems[user_id] = memory_system
    user_memory_configs[user_id] = {
        'api_key': api_key,
        'base_url': base_url,
        'model': model,
        'embedding_model': embedding_model
    }
    return memory_system


# Bearer Token 校验
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header:
            return make_response(401, "未授权：缺少 Authorization 请求头", 2001, None)
        if not auth_header.startswith('Bearer '):
            return make_response(401, "未授权：Authorization 格式错误，应为 'Bearer <token>'", 2002, None)
        token = auth_header.replace('Bearer ', '').strip()

        valid_api_keys = os.environ.get('N8N_API_KEYS', '').strip()
        if valid_api_keys:
            valid_keys = [k.strip() for k in valid_api_keys.split(',')]
            if token not in valid_keys:
                return make_response(401, "未授权：无效的 API Key", 2003, None)
        request.api_key = token
        return f(*args, **kwargs)
    return decorated_function


# /api/memory/search
@app.route('/api/memory/search', methods=['POST'])
@require_api_key
def api_memory_search():
    """调用底层 Memcontext.get_response"""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        user_id = data.get('user_id', '').strip()

        if not query:
            return make_response(400, "query 是必需的参数", 1001, None)
        if not user_id:
            return make_response(400, "user_id 是必需的参数", 1001, None)

        memory_system = get_or_create_memory_system(user_id)

        relationship_with_user = data.get('relationship_with_user', 'friend')
        style_hint = data.get('style_hint', '')
        user_conversation_meta_data = data.get('user_conversation_meta_data')

        response = memory_system.get_response(
            query=query,
            relationship_with_user=relationship_with_user,
            style_hint=style_hint,
            user_conversation_meta_data=user_conversation_meta_data
        )

        return make_response(200, "操作成功", 0, {
            "response": response,
            "timestamp": get_timestamp()
        })
    except Exception as e:
        return make_response(500, f"服务器内部错误: {str(e)}", 5000, None)


# /api/memory/add
@app.route('/api/memory/add', methods=['POST'])
@require_api_key
def api_memory_add():
    """调用底层 Memcontext.add_memory"""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', '').strip()
        user_input = data.get('user_input', '').strip()
        agent_response = data.get('agent_response', '').strip()

        if not user_id:
            return make_response(400, "user_id 是必需的参数", 1001, None)
        if not user_input:
            return make_response(400, "user_input 是必需的参数", 1001, None)
        if not agent_response:
            return make_response(400, "agent_response 是必需的参数", 1001, None)

        memory_system = get_or_create_memory_system(user_id)

        timestamp = data.get('timestamp')
        meta_data = data.get('meta_data')

        memory_system.add_memory(
            user_input=user_input,
            agent_response=agent_response,
            timestamp=timestamp,
            meta_data=meta_data
        )

        short_term_count = len(memory_system.short_term_memory.get_all())
        is_full = memory_system.short_term_memory.is_full()
        response_data = {
            "success": True,
            "message": "记忆已添加到短期记忆" if not is_full else "记忆已添加，短期记忆已满，已自动处理到中期记忆",
            "short_term_count": short_term_count,
            "is_full": is_full,
            "processed_to_mid_term": is_full,
            "timestamp": get_timestamp()
        }
        return make_response(200, "操作成功", 0, response_data)
    except Exception as e:
        return make_response(500, f"服务器内部错误: {str(e)}", 5000, None)


# /api/memory/add_multimodal
@app.route('/api/memory/add_multimodal', methods=['POST'])
@require_api_key
def api_memory_add_multimodal():
    """调用底层 Memcontext.add_multimodal_memory，支持 JSON / multipart"""
    cleanup_paths = []
    try:
        # 读取 user_id
        if request.content_type and 'multipart/form-data' in request.content_type:
            user_id = request.form.get('user_id', '').strip()
        else:
            data = request.get_json(silent=True) or {}
            user_id = data.get('user_id', '').strip()
        if not user_id:
            return make_response(400, "user_id 是必需的参数", 1001, None)
        memory_system = get_or_create_memory_system(user_id)
        converter_type = None
        agent_response = None
        converter_kwargs = {}

        if request.content_type and 'multipart/form-data' in request.content_type:
            uploaded_file = request.files.get('file')
            if not uploaded_file or not uploaded_file.filename:
                return make_response(400, "file 是必需的参数（multipart）", 1001, None)

            safe_name = secure_filename(uploaded_file.filename)
            temp_dir = tempfile.mkdtemp(prefix="memcontext_upload_")
            temp_path = os.path.join(temp_dir, safe_name or "upload.bin")
            uploaded_file.save(temp_path)
            cleanup_paths.append(temp_dir)

            source = temp_path
            source_type = 'file_path'
            agent_response = request.form.get('agent_response')
            converter_type = request.form.get('converter_type')
            if request.form.get('converter_kwargs'):
                try:
                    converter_kwargs = json.loads(request.form['converter_kwargs'])
                except json.JSONDecodeError:
                    return make_response(400, "converter_kwargs 必须是有效的 JSON", 1001, None)
        else:
            data = request.get_json(silent=True) or {}
            if data.get('file_path'):
                source = data['file_path']
                source_type = 'file_path'
            else:
                return make_response(400, "file_path 是必需的参数", 1001, None)
            converter_type = data.get('converter_type')
            agent_response = data.get('agent_response')
            converter_kwargs = data.get('converter_kwargs', {})

        if source_type != 'file_path':
            return make_response(400, "当前仅支持本地文件路径(file_path)", 1003, None)
        if not os.path.exists(source):
            return make_response(400, f"文件路径不存在: {source}", 1003, None)

        converter_type = (converter_type or 'videorag').lower()
        if converter_type not in ('video', 'videorag'):
            return make_response(400, f"不支持的 converter_type: {converter_type}，可选 video | videorag", 1004, None)

        converter_settings = dict(converter_kwargs or {})
        # video 转换器的 API Key 可在 converter_kwargs 传入
        if converter_type == 'video':
            api_key = converter_settings.pop('api_key', None)
            base_url = converter_settings.pop('base_url', None)
            model = converter_settings.pop('model', None)
            if api_key:
                os.environ['LLM_API_KEY'] = api_key
            if base_url:
                os.environ['LLM_BASE_URL'] = base_url
            if model:
                os.environ['LLM_MODEL'] = model

        # 音频转录（SiliconFlow）
        siliconflow_key = converter_settings.pop('siliconflow_key', None)
        if siliconflow_key:
            os.environ['SILICONFLOW_API_KEY'] = siliconflow_key

        converter_settings.setdefault('working_dir', './videorag-workdir')
        progress_events = []

        def progress_callback(progress: float, message: str) -> None:
            progress_events.append({'progress': round(float(progress), 4), 'message': message})

        result = memory_system.add_multimodal_memory(
            source=source,
            source_type=source_type,
            converter_type=converter_type,
            agent_response=agent_response,
            converter_kwargs=converter_settings,
            progress_callback=progress_callback,
        )

        if result.get('status') != 'success':
            return make_response(500, result.get('error', '处理失败'), 5002, {
                "error": result.get('error', '处理失败'),
                "progress": progress_events
            })

        response_data = {
            "success": True,
            "ingested_rounds": result.get('chunks_written', 0),
            "file_id": result.get('file_id'),
            "timestamps": result.get('timestamps', []),
            "progress": progress_events
        }
        if result.get('storage_path'):
            response_data['storage_path'] = result.get('storage_path')
        if result.get('storage_base_path'):
            response_data['storage_base_path'] = result.get('storage_base_path')

        return make_response(200, "操作成功", 0, response_data)
    except Exception as e:
        return make_response(500, f"服务器内部错误: {str(e)}", 5000, None)
    finally:
        for path in cleanup_paths:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass


if __name__ == '__main__':
    # 增加超时时间以支持长时间的视频处理
    # 使用 threaded=True 支持并发请求
    # 注意：Flask 开发服务器可能不支持 request_timeout，但可以通过其他方式处理
    import werkzeug.serving
    werkzeug.serving.WSGIRequestHandler.timeout = 1800  # 30 分钟超时
    app.run(debug=True, host='0.0.0.0', port=5019, threaded=True)

