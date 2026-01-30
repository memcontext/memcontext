# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from concurrent.futures import ThreadPoolExecutor
import atexit
import sys
import os
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
import secrets
from collections import defaultdict
from werkzeug.utils import secure_filename


# 加载配置文件
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

# 增加线程池大小
executor = ThreadPoolExecutor(max_workers=10)

#  Memcontext
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from memcontext import Memcontext
from memcontext.utils import get_timestamp
from memcontext.storage import SupabaseStore

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# CORS 配置
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

memory_systems = {}

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response

# 删除了固定的API_KEY, BASE_URL, MODEL

# 有效邀请码列表 - 在实际部署中应该存储在数据库或加密文件中
# VALID_INVITE_CODES = [
#     'DEMO2024',
#     'MEMORY001',
#     'TESTUSER',
#     'BETA2024',
#     'INVITE123'
# ]

# def load_invite_codes():
#     """从文件加载邀请码列表"""
#     invite_codes_file = os.path.join(os.path.dirname(__file__), 'invite_codes.json')
#     try:
#         if os.path.exists(invite_codes_file):
#             with open(invite_codes_file, 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         else:
#             # 如果文件不存在，创建默认邀请码文件
#             with open(invite_codes_file, 'w', encoding='utf-8') as f:
#                 json.dump(VALID_INVITE_CODES, f, ensure_ascii=False, indent=2)
#             return VALID_INVITE_CODES
#     except Exception as e:
#         print(f"Error loading invite codes: {e}")
#         return VALID_INVITE_CODES

# def save_invite_codes(codes):
#     """保存邀请码列表到文件"""
#     invite_codes_file = os.path.join(os.path.dirname(__file__), 'invite_codes.json')
#     try:
#         with open(invite_codes_file, 'w', encoding='utf-8') as f:
#             json.dump(codes, f, ensure_ascii=False, indent=2)
#     except Exception as e:
#         print(f"Error saving invite codes: {e}")

# 启动时加载邀请码
# VALID_INVITE_CODES = load_invite_codes()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/init_memory', methods=['POST'])
def init_memory():
    data = request.json

    user_id = data.get('user_id', '').strip() or GLOBAL_CONFIG.get("user_id", "default_user")
    
    if not user_id:
        return jsonify({'error': 'User ID 是必需的。'}), 400
    
    # 直接从 GLOBAL_CONFIG 获取参数
    assistant_id = GLOBAL_CONFIG.get("assistant_id") or f"assistant_{user_id}"
    api_key = GLOBAL_CONFIG.get("openai_api_key", "")
    base_url = GLOBAL_CONFIG.get("openai_base_url", "https://api.openai.com/v1")
    model = GLOBAL_CONFIG.get("llm_model", "gpt-4o-mini")
    data_path = GLOBAL_CONFIG.get("data_storage_path", "./data")
    embedding_api_key = GLOBAL_CONFIG.get("embedding_api_key", "")
    embedding_base_url = GLOBAL_CONFIG.get("embedding_base_url", "https://ark.cn-beijing.volces.com/api/v3")
    api_urls_keys = GLOBAL_CONFIG.get("openai_api_urls_keys", {})

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

    try:
        os.makedirs(data_path, exist_ok=True)
        
        file_storage_base_path = data.get('file_storage_base_path', '').strip()
        if not file_storage_base_path:
            file_storage_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        # 初始化 Memcontext
        memory_system = Memcontext(
            user_id=user_id,
            openai_api_key=api_key,
            openai_base_url=base_url,
            assistant_id=assistant_id,
            short_term_capacity=GLOBAL_CONFIG.get("short_term_capacity", 7),
            mid_term_capacity=GLOBAL_CONFIG.get("mid_term_capacity", 200),
            long_term_knowledge_capacity=GLOBAL_CONFIG.get("long_term_knowledge_capacity", 100),
            data_storage_path=data_path,
            mid_term_heat_threshold=GLOBAL_CONFIG.get("mid_term_heat_threshold", 7.0),
            llm_model=model,
            embedding_model_name=GLOBAL_CONFIG.get("embedding_model_name", "all-MiniLM-L6-v2"),
            embedding_model_kwargs={"api_key":embedding_api_key, "base_url":embedding_base_url},
            file_storage_base_path=file_storage_base_path,
            openai_api_urls_keys=api_urls_keys,
            storage=supa_store,
        )
        
        session_id = secrets.token_hex(8)
        memory_systems[session_id] = memory_system
        session['memory_session_id'] = session_id
        
        # 存入 Session 供 clear_memory 复用
        session['memory_config'] = {
            'user_id': user_id,
            'api_urls_keys': api_urls_keys,
            'data_path': data_path,
            'assistant_id': assistant_id,
            'model': model,
            'raw_config': GLOBAL_CONFIG 
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'user_id': user_id,
            'assistant_id': assistant_id,
            'model': model,
            'base_url': base_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_user_tags(memory_system):
    user_profile = memory_system.user_long_term_memory.get_raw_user_profile(memory_system.user_id)
    if not user_profile or user_profile.lower() in ["null", "none", "no profile data yet"]:
        return {'interests':[], "personality_traits":[]}
    try:
        personality_traits = parse_personality_traits(user_profile)
        interests_tags = personality_traits.get("Content Platform Interest Tags", [])
        user_interests = []
        for interest in interests_tags:
            level = interest.get("level", "").lower()
            dimension = interest.get("dimension", "")
            if level in ["high", "medium"] and dimension:
                interest = dimension.replace("Interest", "").replace("Concern", "").replace("Activity", "").strip()
                if interest:
                    user_interests.append(interest)
        psychological_traits = personality_traits.get("Psychological Model", [])
        user_personality_traits = []
        for trait in psychological_traits:
            level = trait.get("level", "").lower()
            dimension = trait.get("dimension", "")
            if level in ["high", "medium"] and dimension:
                trait = dimension.replace("Need for", "").replace("Need", "").strip()
                if trait:
                    user_personality_traits.append(trait)
        return {'interests':user_interests, "personality_traits":user_personality_traits}
    except Exception as e:
        print(f"DEBUG [Ad]: Error getting user tags: {e}", flush=True)
        return {'interests':[], "personality_traits":[]}

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '')
    session_id = session.get('memory_session_id')
    
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    
    memory_system = memory_systems[session_id]

    def generate():
        interest_tag = get_user_tags(memory_system)
        print("interest_tag:", interest_tag, flush=True)
        try:
            for chunk in memory_system.get_response_stream(user_input):
                yield f"data: {json.dumps({'response': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'text_done': True})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            print(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/import_from_cache', methods=['POST'])
def import_from_cache_endpoint():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400

    memory_system = memory_systems[session_id]
    
    try:
        data = request.get_json(silent=True) or {}
        file_id = data.get('file_id', '').strip()
        
        if not file_id:
            return jsonify({'error': 'file_id is required'}), 400
        
        cache_dir = Path(memory_system.data_storage_path) / "temp_memory"
        cache_file = cache_dir / f"{file_id}.json"
        
        if not cache_file.exists():
            return jsonify({'error': f'Cache file not found for file_id: {file_id}'}), 404
        
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        
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
        
        base_metadata = cached.get("metadata", {})
        timestamps = []
        memories_to_add = []
        
        for chunk in output.chunks:
            try:
                base_meta = base_metadata if isinstance(base_metadata, dict) else {}
                chunk_meta_dict = chunk.metadata if isinstance(chunk.metadata, dict) else {}
                chunk_meta = {**base_meta, **chunk_meta_dict, "source_type": "multimodal"}
            except (TypeError, AttributeError) as e:
                chunk_meta = {"source_type": "multimodal"}
            
            if chunk_meta.get("video_path") or chunk_meta.get("video_name"):
                chunk_agent_response = chunk.text
            else:
                chunk_agent_response = chunk_meta.get("chunk_summary", f"[Multimodal] Stored content")
            
            try:
                video_path = chunk_meta.get("video_path") or chunk_meta.get("original_filename") or chunk_meta.get("video_name") or "视频"
                time_range = chunk_meta.get("time_range", "")
                if (chunk_meta.get("video_path") or chunk_meta.get("video_name")) and time_range:
                    if not isinstance(video_path, str) or not video_path or video_path == "视频":
                        video_path = chunk_meta.get("video_name") or chunk_meta.get("original_filename") or "视频"
                    user_input = f"描述{video_path}视频的{time_range}的内容"
                else:
                    user_input = chunk.text
            except Exception:
                user_input = chunk.text
            
            memories_to_add.append({
                "user_input": user_input,
                "agent_response": chunk_agent_response,
                "timestamp": get_timestamp(),
                "meta_data": chunk_meta,
            })
            timestamps.append(get_timestamp())
        
        for mem in memories_to_add:
            memory_system.add_memory(
                user_input=mem["user_input"],
                agent_response=mem["agent_response"],
                timestamp=mem["timestamp"],
                meta_data=mem["meta_data"]
            )
        
        return jsonify({
            'success': True,
            'ingested_rounds': len(memories_to_add),
            'file_id': file_id,
            'timestamps': timestamps,
            'message': f'Successfully imported {len(memories_to_add)} chunks from cache'
        })
    except Exception as e:
        import traceback
        return jsonify({'error': f'导入缓存失败: {str(e)}', 'traceback': traceback.format_exc() if app.debug else None}), 500

@app.route('/add_multimodal_memory_stream', methods=['POST'])
def add_multimodal_memory_stream():
    from flask import Response, stream_with_context
    import queue
    import threading
    
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        def error_gen(): yield f"data: {json.dumps({'error': 'Memory system not initialized'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    memory_system = memory_systems[session_id]
    data = request.get_json(silent=True) or {}
    file_path = data.get('file_path')
    converter_type = (data.get('converter_type') or 'video').lower()
    agent_response = data.get('agent_response')
    converter_kwargs = data.get('converter_kwargs', {})
    
    if not file_path:
        def error_gen(): yield f"data: {json.dumps({'error': 'file_path is required'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    progress_queue = queue.Queue()
    def progress_callback(progress: float, message: str) -> None:
        progress_queue.put({'progress': round(float(progress), 4), 'message': message})
    
    result_holder = {'result': None, 'error': None}
    
    def process_video():
        try:
            converter_settings = dict(converter_kwargs or {})
            converter_settings.setdefault('working_dir', './videorag-workdir')
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
            progress_queue.put(None)
    
    def generate():
        thread = threading.Thread(target=process_video)
        thread.start()
        while True:
            try:
                item = progress_queue.get(timeout=0.5)
                if item is None: break
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        thread.join()
        if result_holder['error']:
            yield f"data: {json.dumps({'done': True, 'error': result_holder['error']})}\n\n"
        else:
            res = result_holder['result']
            yield f"data: {json.dumps({'done': True, 'success': True, 'chunks_written': res.get('chunks_written', 0), 'file_id': res.get('file_id')})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/add_multimodal_memory', methods=['POST'])
def add_multimodal_memory_endpoint():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400

    memory_system = memory_systems[session_id]
    cleanup_paths = []

    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
             uploaded_file = request.files.get('file')
             safe_name = secure_filename(uploaded_file.filename)
             temp_dir = tempfile.mkdtemp()
             temp_path = os.path.join(temp_dir, safe_name)
             uploaded_file.save(temp_path)
             cleanup_paths.append(temp_dir)
             source = temp_path
             source_type = 'file_path'
             converter_type = request.form.get('converter_type', 'videorag')
             converter_kwargs = {}
        else:
             data = request.json or {}
             source = data.get('file_path')
             source_type = 'file_path'
             converter_type = data.get('converter_type', 'videorag')
             converter_kwargs = data.get('converter_kwargs', {})

        converter_settings = dict(converter_kwargs)
        converter_settings.setdefault('working_dir', './videorag-workdir')
        progress_events = []
        def progress_callback(p, m): progress_events.append({'progress': p, 'message': m})

        result = memory_system.add_multimodal_memory(
            source=source, source_type=source_type, converter_type=converter_type,
            converter_kwargs=converter_settings, progress_callback=progress_callback
        )
        
        if result.get('status') != 'success': return jsonify({'error': result.get('error'), 'progress': progress_events}), 500
        return jsonify({'success': True, 'progress': progress_events, 'file_id': result.get('file_id')})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        for path in cleanup_paths: shutil.rmtree(path, ignore_errors=True)

@app.route('/memory_state', methods=['GET'])
def get_memory_state():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    
    memory_system = memory_systems[session_id]
    try:
        short_term = memory_system.short_term_memory.get_all()
        mid_term_sessions = []
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
        mid_term_sessions.sort(key=lambda x: x['heat'], reverse=True)
        
        user_profile = memory_system.user_long_term_memory.get_raw_user_profile(memory_system.user_id)
        user_knowledge = memory_system.user_long_term_memory.get_user_knowledge()
        assistant_knowledge = memory_system.assistant_long_term_memory.get_assistant_knowledge(user_id=memory_system.user_id)
        
        return jsonify({
            'short_term': {'current_count': len(short_term), 'memories': short_term},
            'mid_term': {'current_count': len(memory_system.mid_term_memory.sessions), 'sessions': mid_term_sessions},
            'long_term': {
                'user_profile': user_profile,
                'user_knowledge': [k.get('knowledge') for k in user_knowledge],
                'assistant_knowledge': [k.get('knowledge') for k in assistant_knowledge]
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/trigger_analysis', methods=['POST'])
def trigger_analysis():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    memory_system = memory_systems[session_id]
    try:
        memory_system.force_mid_term_analysis()
        return jsonify({'success': True, 'message': 'Analysis triggered successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/personality_analysis', methods=['POST'])
def personality_analysis():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    memory_system = memory_systems[session_id]
    try:
        user_profile = memory_system.user_long_term_memory.get_raw_user_profile(memory_system.user_id)
        return jsonify({'success': True, 'personality_analysis': parse_personality_traits(user_profile)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
# clear_memory: 使用 Session 中的配置缓存
@app.route('/clear_memory', methods=['POST'])
def clear_memory():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    
    memory_system = memory_systems[session_id]
    
    try:
        if os.path.exists(memory_system.user_data_dir): shutil.rmtree(memory_system.user_data_dir)
        if os.path.exists(memory_system.assistant_data_dir): shutil.rmtree(memory_system.assistant_data_dir)
        
        if hasattr(memory_system, 'client') and hasattr(memory_system.client, 'shutdown'):
            memory_system.client.shutdown()
            try:
                atexit.unregister(memory_system.client.shutdown)
            except:
                pass
        
        # 从 Session 中获取初始化时保存的配置
        sess_cfg = session.get('memory_config', {})
        # raw_config 是 GLOBAL_CONFIG 的副本
        raw_config = sess_cfg.get('raw_config', GLOBAL_CONFIG)

        # Supabase 配置（与 init_memory 保持一致）
        supa_cfg = raw_config.get("supabase", {}) or {}
        supa_url = supa_cfg.get("url")
        supa_key = supa_cfg.get("service_key")
        supa_schema = supa_cfg.get("schema", "public")
        supa_sessions_table = supa_cfg.get("mid_sessions_table", "sessions")
        supa_pages_table = supa_cfg.get("mid_pages_table", "pages")
        ltm_user_profiles_table = supa_cfg.get("ltm_user_profiles_table", "long_term_user_profiles")
        ltm_user_knowledge_table = supa_cfg.get("ltm_user_knowledge_table", "long_term_user_knowledge")
        ltm_assistant_knowledge_table = supa_cfg.get("ltm_assistant_knowledge_table", "long_term_assistant_knowledge")

        # 从 config 读取 Postgres 连接信息
        postgres_host = supa_cfg.get("postgres_host")
        postgres_port = supa_cfg.get("postgres_port", 5432)
        postgres_db = supa_cfg.get("postgres_db", "postgres")
        postgres_user = supa_cfg.get("postgres_user", "postgres")
        postgres_password = supa_cfg.get("postgres_password")
        postgres_connection_string = supa_cfg.get("postgres_connection_string")

        supa_store = None
        if supa_url and supa_key:
            try:
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
                print(f"SupabaseStore re-initialized for mid-term memory in clear_memory: {supa_url}")
            except Exception as e:
                print(f"Warning: Failed to re-initialize SupabaseStore in clear_memory, fallback to local mid_term.json. Error: {e}")

        # 重建 Memcontext
        new_memory_system = Memcontext(
            user_id=memory_system.user_id,
            openai_api_key=sess_cfg.get('api_key', raw_config.get("openai_api_key", "")),
            openai_base_url=sess_cfg.get('base_url', raw_config.get("openai_base_url", "https://api.openai.com/v1")),
            openai_api_urls_keys=sess_cfg.get('openai_api_urls_keys') or GLOBAL_CONFIG.get("openai_api_urls_keys", {}),
            data_storage_path=sess_cfg.get('data_path', raw_config.get("data_storage_path", "./data")),
            assistant_id=memory_system.assistant_id,
            short_term_capacity=raw_config.get("short_term_capacity", 7),
            mid_term_capacity=raw_config.get("mid_term_capacity", 200),
            long_term_knowledge_capacity=raw_config.get("long_term_knowledge_capacity", 100),
            mid_term_heat_threshold=raw_config.get("mid_term_heat_threshold", 7.0),
            llm_model=sess_cfg.get('model', raw_config.get("llm_model")),
            embedding_model_name=raw_config.get("embedding_model_name", "all-MiniLM-L6-v2"), 
            embedding_model_kwargs={
                "api_key": raw_config.get("embedding_api_key", ""),
                "base_url": raw_config.get("embedding_base_url", "https://ark.cn-beijing.volces.com/api/v3"),
            },
            storage=supa_store,
        )
        
        memory_systems[session_id] = new_memory_system
        return jsonify({'success': True, 'message': 'All memories cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/import_conversations', methods=['POST'])
def import_conversations():
    session_id = session.get('memory_session_id')
    if not session_id or session_id not in memory_systems:
        return jsonify({'error': 'Memory system not initialized'}), 400
    memory_system = memory_systems[session_id]
    data = request.json
    try:
        imported_count = 0
        for conv in data.get('conversations', []):
            if conv.get('user_input') and conv.get('agent_response'):
                memory_system.add_memory(
                    user_input=conv.get('user_input'),
                    agent_response=conv.get('agent_response'),
                    timestamp=conv.get('timestamp', get_timestamp())
                )
                imported_count += 1
        return jsonify({'success': True, 'imported_count': imported_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5019)