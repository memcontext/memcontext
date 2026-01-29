import json
import numpy as np
from collections import defaultdict
import faiss
import heapq
from datetime import datetime
from typing import Optional

from .utils import (
    get_timestamp, generate_id, get_embedding, normalize_vector,
    compute_time_decay, ensure_directory_exists, OpenAIClient
)
from .storage import MemoryStorage

# Heat computation constants (can be tuned or made configurable)
HEAT_ALPHA = 1.0
HEAT_BETA = 1.0
HEAT_GAMMA = 1
RECENCY_TAU_HOURS = 24 # For R_recency calculation in compute_segment_heat

def compute_segment_heat(session, alpha=HEAT_ALPHA, beta=HEAT_BETA, gamma=HEAT_GAMMA, tau_hours=RECENCY_TAU_HOURS):
    N_visit = session.get("N_visit", 0)
    L_interaction = session.get("L_interaction", 0)
    
    # Calculate recency based on last_visit_time
    R_recency = 1.0 # Default if no last_visit_time
    if session.get("last_visit_time"):
        R_recency = compute_time_decay(session["last_visit_time"], get_timestamp(), tau_hours)
    
    session["R_recency"] = R_recency # Update session's recency factor
    return alpha * N_visit + beta * L_interaction + gamma * R_recency

class MidTermMemory:
    def __init__(
        self,
        file_path: str,
        client: OpenAIClient,
        max_capacity: int = 2000,
        embedding_model_name: str = "all-MiniLM-L6-v2",
        embedding_model_kwargs: Optional[dict] = None,
        storage: Optional[MemoryStorage] = None,
        user_id: Optional[str] = None,
    ):
        """
        如果提供了 storage + user_id，则所有持久化和检索优先走存储后端（如 SupabaseStore）；
        否则回退到原来的本地 JSON 文件 + FAISS 方案。
        """
        self.file_path = file_path
        # 仅在本地文件模式下需要确保目录存在
        if storage is None:
            ensure_directory_exists(self.file_path)

        self.client = client
        self.max_capacity = max_capacity
        self.sessions = {}  # {session_id: session_object}
        self.access_frequency = defaultdict(int)  # {session_id: access_count_for_lfu}
        self.heap = []  # Min-heap storing (-H_segment, session_id) for hottest segments

        self.embedding_model_name = embedding_model_name
        self.embedding_model_kwargs = embedding_model_kwargs if embedding_model_kwargs is not None else {}

        self.storage: Optional[MemoryStorage] = storage
        self.user_id: Optional[str] = user_id

        self.load()

    def get_page_by_id(self, page_id):
        for session in self.sessions.values():
            for page in session.get("details", []):
                if page.get("page_id") == page_id:
                    return page
        return None

    def update_page_connections(self, prev_page_id, next_page_id):
        if prev_page_id:
            prev_page = self.get_page_by_id(prev_page_id)
            if prev_page:
                prev_page["next_page"] = next_page_id
        if next_page_id:
            next_page = self.get_page_by_id(next_page_id)
            if next_page:
                next_page["pre_page"] = prev_page_id
        # self.save() # Avoid saving on every minor update; save at higher level operations

    def evict_lfu(self):
        if not self.access_frequency or not self.sessions:
            return
        
        lfu_sid = min(self.access_frequency, key=self.access_frequency.get)
        print(f"MidTermMemory: LFU eviction. Session {lfu_sid} has lowest access frequency.")
        
        if lfu_sid not in self.sessions:
            del self.access_frequency[lfu_sid] # Clean up access frequency if session already gone
            self.rebuild_heap()
            return
        
        session_to_delete = self.sessions.pop(lfu_sid) # Remove from sessions
        del self.access_frequency[lfu_sid] # Remove from LFU tracking

        # Clean up page connections if this session's pages were linked
        for page in session_to_delete.get("details", []):
            prev_page_id = page.get("pre_page")
            next_page_id = page.get("next_page")
            # If a page from this session was linked to an external page, nullify the external link
            if prev_page_id and not self.get_page_by_id(prev_page_id): # Check if prev page is still in memory
                 # This case should ideally not happen if connections are within sessions or handled carefully
                 pass 
            if next_page_id and not self.get_page_by_id(next_page_id):
                 pass
            # More robustly, one might need to search all other sessions if inter-session linking was allowed
            # For now, assuming internal consistency or that Memcontext class manages higher-level links

        self.rebuild_heap()

        # 如果有存储后端，通知其删除；否则回退到本地 save()
        if self.storage is not None and self.user_id is not None:
            try:
                self.storage.delete_session(self.user_id, lfu_sid)
            except Exception as e:
                print(f"MidTermMemory: Error deleting session {lfu_sid} from storage: {e}")
        else:
            self.save()
        print(f"MidTermMemory: Evicted session {lfu_sid}.")
# NOTE 如果没有相似度得分大于0.6的匹配对话就add-session
    def add_session(self, summary, details, summary_keywords=None):
        session_id = generate_id("session")
        summary_vec = get_embedding(
            summary, 
            model_name=self.embedding_model_name, 
            **self.embedding_model_kwargs
        )
        summary_vec = normalize_vector(summary_vec).tolist()
        summary_keywords = summary_keywords if summary_keywords is not None else []
        
        processed_details = []
        for page_data in details:
            page_id = page_data.get("page_id", generate_id("page"))
            
            # 检查是否已有embedding，避免重复计算
            if "page_embedding" in page_data and page_data["page_embedding"]:
                print(f"MidTermMemory: Reusing existing embedding for page {page_id}")
                inp_vec = page_data["page_embedding"]
                # 确保embedding是normalized的
                if isinstance(inp_vec, list):
                    inp_vec_np = np.array(inp_vec, dtype=np.float32)
                    if np.linalg.norm(inp_vec_np) > 1.1 or np.linalg.norm(inp_vec_np) < 0.9:  # 检查是否需要重新normalize
                        inp_vec = normalize_vector(inp_vec_np).tolist()
            else:
                print(f"MidTermMemory: Computing new embedding for page {page_id}")
                full_text = f"User: {page_data.get('user_input','')} Assistant: {page_data.get('agent_response','')}"
                inp_vec = get_embedding(
                    full_text,
                    model_name=self.embedding_model_name,
                    **self.embedding_model_kwargs
                )
                inp_vec = normalize_vector(inp_vec).tolist()
            
            # 使用已有keywords或设置为空（由multi-summary提供）
            if "page_keywords" in page_data and page_data["page_keywords"]:
                print(f"MidTermMemory: Using existing keywords for page {page_id}")
                page_keywords = page_data["page_keywords"]
            else:
                print(f"MidTermMemory: Setting empty keywords for page {page_id} (will be filled by multi-summary)")
                page_keywords = []
            
            processed_page = {
                **page_data, # Carry over existing fields like user_input, agent_response, timestamp
                "page_id": page_id,
                "page_embedding": inp_vec,
                "page_keywords": page_keywords,
                "preloaded": page_data.get("preloaded", False), # Preserve if passed
                "analyzed": page_data.get("analyzed", False),   # Preserve if passed
                # pre_page, next_page, meta_info are handled by DynamicUpdater
            }
            processed_details.append(processed_page)
        
        current_ts = get_timestamp()
        session_obj = {
            "id": session_id,
            "summary": summary,
            "summary_keywords": summary_keywords,
            "summary_embedding": summary_vec,
            "details": processed_details,
            "L_interaction": len(processed_details),
            "R_recency": 1.0, # Initial recency
            "N_visit": 0,
            "H_segment": 0.0, # Initial heat, will be computed
            "timestamp": current_ts, # Creation timestamp
            "last_visit_time": current_ts, # Also initial last_visit_time for recency calc
            "access_count_lfu": 0 # For LFU eviction policy
        }
        session_obj["H_segment"] = compute_segment_heat(session_obj)
        self.sessions[session_id] = session_obj
        self.access_frequency[session_id] = 0 # Initialize for LFU
        heapq.heappush(self.heap, (-session_obj["H_segment"], session_id)) # Use negative heat for max-heap behavior
        
        print(f"MidTermMemory: Added new session {session_id}. Initial heat: {session_obj['H_segment']:.2f}.")
        if len(self.sessions) > self.max_capacity:
            self.evict_lfu()

        # 落库：有 storage 时优先调用存储后端，否则回退到本地 JSON
        if self.storage is not None and self.user_id is not None:
            try:
                self.storage.upsert_session_with_pages(
                    user_id=self.user_id,
                    session=session_obj,
                    pages=processed_details,
                )
            except Exception as e:
                print(f"MidTermMemory: Error upserting session {session_id} to storage: {e}")
        else:
            self.save()

        return session_id

    def rebuild_heap(self):
        self.heap = []
        for sid, session_data in self.sessions.items():
            # Ensure H_segment is up-to-date before rebuilding heap if necessary
            # session_data["H_segment"] = compute_segment_heat(session_data)
            heapq.heappush(self.heap, (-session_data["H_segment"], sid))
        # heapq.heapify(self.heap) # Not needed if pushing one by one
        # No save here, it's an internal operation often followed by other ops that save

    def insert_pages_into_session(self, summary_for_new_pages, keywords_for_new_pages, pages_to_insert, 
                                  similarity_threshold=0.6, keyword_similarity_alpha=1.0):
        if not self.sessions: # If no existing sessions, just add as a new one
            print("MidTermMemory: No existing sessions. Adding new session directly.")
            return self.add_session(summary_for_new_pages, pages_to_insert, keywords_for_new_pages)

        new_summary_vec = get_embedding(
            summary_for_new_pages,
            model_name=self.embedding_model_name,
            **self.embedding_model_kwargs
        )
        new_summary_vec = normalize_vector(new_summary_vec)
        
        best_sid = None
        best_overall_score = -1
# TODO 改成到superbase数据库检索与page最相关session
        for sid, existing_session in self.sessions.items():
            existing_summary_vec = np.array(existing_session["summary_embedding"], dtype=np.float32)
            semantic_sim = float(np.dot(existing_summary_vec, new_summary_vec))
            
            # Keyword similarity (Jaccard index based)
            existing_keywords = set(existing_session.get("summary_keywords", []))
            new_keywords_set = set(keywords_for_new_pages)
            s_topic_keywords = 0
            if existing_keywords and new_keywords_set:
                intersection = len(existing_keywords.intersection(new_keywords_set))
                union = len(existing_keywords.union(new_keywords_set))
                if union > 0:
                    s_topic_keywords = intersection / union 
            
            overall_score = semantic_sim + keyword_similarity_alpha * s_topic_keywords
            
            if overall_score > best_overall_score:
                best_overall_score = overall_score
                best_sid = sid
        
        if best_sid and best_overall_score >= similarity_threshold:
            print(f"MidTermMemory: Merging pages into session {best_sid}. Score: {best_overall_score:.2f} (Threshold: {similarity_threshold})")
            target_session = self.sessions[best_sid]
            
            processed_new_pages = []
            for page_data in pages_to_insert:
                page_id = page_data.get("page_id", generate_id("page")) # Use existing or generate new ID
                
                # 检查是否已有embedding，避免重复计算
                if "page_embedding" in page_data and page_data["page_embedding"]:
                    print(f"MidTermMemory: Reusing existing embedding for page {page_id}")
                    inp_vec = page_data["page_embedding"]
                    # 确保embedding是normalized的
                    if isinstance(inp_vec, list):
                        inp_vec_np = np.array(inp_vec, dtype=np.float32)
                        if np.linalg.norm(inp_vec_np) > 1.1 or np.linalg.norm(inp_vec_np) < 0.9:  # 检查是否需要重新normalize
                            inp_vec = normalize_vector(inp_vec_np).tolist()
                else:
                    print(f"MidTermMemory: Computing new embedding for page {page_id}")
                    full_text = f"User: {page_data.get('user_input','')} Assistant: {page_data.get('agent_response','')}"
                    inp_vec = get_embedding(
                        full_text,
                        model_name=self.embedding_model_name,
                        **self.embedding_model_kwargs
                    )
                    inp_vec = normalize_vector(inp_vec).tolist()
                
                # 使用已有keywords或继承session的keywords
                if "page_keywords" in page_data and page_data["page_keywords"]:
                    print(f"MidTermMemory: Using existing keywords for page {page_id}")
                    page_keywords_current = page_data["page_keywords"]
                else:
                    print(f"MidTermMemory: Using session keywords for page {page_id}")
                    page_keywords_current = keywords_for_new_pages

                processed_page = {
                    **page_data, # Carry over existing fields
                    "page_id": page_id,
                    "page_embedding": inp_vec,
                    "page_keywords": page_keywords_current,
                    # analyzed, preloaded flags should be part of page_data if set
                }
                target_session["details"].append(processed_page)
                processed_new_pages.append(processed_page)

            target_session["L_interaction"] += len(pages_to_insert)
            target_session["last_visit_time"] = get_timestamp() # Update last visit time on modification
            target_session["H_segment"] = compute_segment_heat(target_session)
            self.rebuild_heap() # Rebuild heap as heat has changed

            # 同步到存储后端
            if self.storage is not None and self.user_id is not None:
                try:
                    self.storage.append_pages_to_session(
                        user_id=self.user_id,
                        session_id=best_sid,
                        pages=processed_new_pages,
                    )
                    self.storage.update_session_stats(
                        user_id=self.user_id,
                        session_id=best_sid,
                        stats={
                            "L_interaction": target_session.get("L_interaction", 0),
                            "N_visit": target_session.get("N_visit", 0),
                            "R_recency": target_session.get("R_recency", 1.0),
                            "H_segment": target_session.get("H_segment", 0.0),
                            "last_visit_time": target_session.get("last_visit_time"),
                            "access_count_lfu": target_session.get("access_count_lfu", 0),
                        },
                    )
                except Exception as e:
                    print(f"MidTermMemory: Error updating storage for session {best_sid}: {e}")
            else:
                self.save()
            return best_sid
        else:
            print(f"MidTermMemory: No suitable session to merge (best score {best_overall_score:.2f} < threshold {similarity_threshold}). Creating new session.")
            return self.add_session(summary_for_new_pages, pages_to_insert, keywords_for_new_pages)

    def search_sessions(
        self,
        query_text,
        segment_similarity_threshold: float = 0.1,
        page_similarity_threshold: float = 0.1,
        top_k_sessions: int = 5,
        keyword_alpha: float = 1.0,
        recency_tau_search: float = 3600,
    ):
        """
        如果配置了存储后端（如 SupabaseStore），则优先委托给 storage.search_sessions_by_embedding；
        否则保留原有的本地 FAISS 检索逻辑。
        """
        # 先统一生成 query 向量
        query_vec = get_embedding(
            query_text,
            model_name=self.embedding_model_name,
            **self.embedding_model_kwargs
        )
        query_vec = normalize_vector(query_vec)

        # --- 优先走存储后端 ---
        if self.storage is not None and self.user_id is not None:
            try:
                results = self.storage.search_sessions_by_embedding(
                    user_id=self.user_id,
                    query_embedding=query_vec,
                    segment_similarity_threshold=segment_similarity_threshold,
                    page_similarity_threshold=page_similarity_threshold,
                    top_k_sessions=top_k_sessions,
                    keyword_alpha=keyword_alpha,
                    query_keywords=[],
                )

                # 本地更新访问统计和热度
                current_time_str = get_timestamp()
                for item in results:
                    sid = item.get("session_id")
                    if sid and sid in self.sessions:
                        session = self.sessions[sid]
                        session["N_visit"] = session.get("N_visit", 0) + 1
                        session["last_visit_time"] = current_time_str
                        session["access_count_lfu"] = session.get("access_count_lfu", 0) + 1
                        self.access_frequency[sid] = session["access_count_lfu"]
                        session["H_segment"] = compute_segment_heat(session)

                        # 将统计同步回存储
                        try:
                            self.storage.update_session_stats(
                                user_id=self.user_id,
                                session_id=sid,
                                stats={
                                    "N_visit": session["N_visit"],
                                    "L_interaction": session.get("L_interaction", 0),
                                    "R_recency": session.get("R_recency", 1.0),
                                    "H_segment": session["H_segment"],
                                    "last_visit_time": session["last_visit_time"],
                                    "access_count_lfu": session["access_count_lfu"],
                                },
                            )
                        except Exception as e:
                            print(f"MidTermMemory: Error updating stats for session {sid} in storage: {e}")

                self.rebuild_heap()
                return results
            except Exception as e:
                print(f"MidTermMemory: Error searching via storage, fallback to local search. Error: {e}")

        # --- 本地 FAISS 检索（兼容原有逻辑） ---
        if not self.sessions:
            return []

        query_keywords = set()  # Keywords extraction removed, relying on semantic similarity

        session_ids = list(self.sessions.keys())
        if not session_ids:
            return []

        summary_embeddings_list = [self.sessions[s]["summary_embedding"] for s in session_ids]
        summary_embeddings_np = np.array(summary_embeddings_list, dtype=np.float32)

        dim = summary_embeddings_np.shape[1]
        index = faiss.IndexFlatIP(dim) # Inner product for similarity
        index.add(summary_embeddings_np)
        
        query_arr_np = np.array([query_vec], dtype=np.float32)
        distances, indices = index.search(query_arr_np, min(top_k_sessions, len(session_ids)))

        results = []
        current_time_str = get_timestamp()

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            
            session_id = session_ids[idx]
            session = self.sessions[session_id]
            semantic_sim_score = float(distances[0][i]) # This is the dot product

            # Keyword similarity for session summary
            session_keywords = set(session.get("summary_keywords", []))
            s_topic_keywords = 0
            if query_keywords and session_keywords:
                intersection = len(query_keywords.intersection(session_keywords))
                union = len(query_keywords.union(session_keywords))
                if union > 0:
                    s_topic_keywords = intersection / union
            
            # Time decay for session recency in search scoring
            # time_decay_factor = compute_time_decay(session["timestamp"], current_time_str, tau_hours=recency_tau_search)
            
            # Combined score for session relevance
            session_relevance_score =  (semantic_sim_score + keyword_alpha * s_topic_keywords)

            if session_relevance_score >= segment_similarity_threshold:
                matched_pages_in_session = []
                for page in session.get("details", []):
                    page_embedding = np.array(page["page_embedding"], dtype=np.float32)
                    
                    page_sim_score = float(np.dot(page_embedding, query_vec))

                    if page_sim_score >= page_similarity_threshold:
                        matched_pages_in_session.append({"page_data": page, "score": page_sim_score})
                
                if matched_pages_in_session:
                    # Update session access stats
                    session["N_visit"] += 1
                    session["last_visit_time"] = current_time_str
                    session["access_count_lfu"] = session.get("access_count_lfu", 0) + 1
                    self.access_frequency[session_id] = session["access_count_lfu"]
                    session["H_segment"] = compute_segment_heat(session)
                    self.rebuild_heap() # Heat changed
                    
                    results.append({
                        "session_id": session_id,
                        "session_summary": session["summary"],
                        "session_relevance_score": session_relevance_score,
                        "matched_pages": sorted(matched_pages_in_session, key=lambda x: x["score"], reverse=True) # Sort pages by score
                    })
        
        self.save() # Save changes from access updates
        # Sort final results by session_relevance_score
        return sorted(results, key=lambda x: x["session_relevance_score"], reverse=True)
    def save(self):
        """
        持久化当前 sessions 状态：
        - 如果配置了 storage，则调用 save_session_batch；
        - 否则回退到本地 JSON 文件写入。
        """
        if self.storage is not None and self.user_id is not None:
            try:
                self.storage.save_session_batch(
                    user_id=self.user_id,
                    sessions=self.sessions.values(),
                )
            except Exception as e:
                print(f"MidTermMemory: Error saving sessions to storage: {e}")
            return

        # 本地 JSON 模式
        data_to_save = {
            "sessions": self.sessions,
            "access_frequency": dict(self.access_frequency), # Convert defaultdict to dict for JSON
        }
        try:
            ensure_directory_exists(self.file_path)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error saving MidTermMemory to {self.file_path}: {e}")

    def load(self):
        """
        从存储加载 sessions：
        - 如果配置了 storage，则调用 load_sessions_meta；
        - 否则回退到本地 JSON 文件读取。
        """
        if self.storage is not None and self.user_id is not None:
            try:
                meta = self.storage.load_sessions_meta(self.user_id)
                self.sessions = dict(meta)
                # Supabase 等外部存储的 meta 可能不包含 pages 明细；下游流程会访问 session["details"]
                # 这里先补默认值，避免 KeyError；如需完整 pages，可在后续按 session_id 再取 pages 表
                for _sid, _s in self.sessions.items():
                    if isinstance(_s, dict):
                        _s.setdefault("details", [])
                # 从 meta 中恢复 access_frequency
                self.access_frequency = defaultdict(
                    int,
                    {
                        sid: s.get("access_count_lfu", 0)
                        for sid, s in self.sessions.items()
                    },
                )
                self.rebuild_heap()
                print(f"MidTermMemory: Loaded from storage for user {self.user_id}. Sessions: {len(self.sessions)}.")
                return
            except Exception as e:
                print(f"MidTermMemory: Error loading from storage, fallback to local file. Error: {e}")

        # 本地 JSON 模式
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.sessions = data.get("sessions", {})
                self.access_frequency = defaultdict(int, data.get("access_frequency", {}))
                self.rebuild_heap() # Rebuild heap from loaded sessions
            print(f"MidTermMemory: Loaded from {self.file_path}. Sessions: {len(self.sessions)}.")
        except FileNotFoundError:
            print(f"MidTermMemory: No history file found at {self.file_path}. Initializing new memory.")
        except json.JSONDecodeError:
            print(f"MidTermMemory: Error decoding JSON from {self.file_path}. Initializing new memory.")
        except Exception as e:
            print(f"MidTermMemory: An unexpected error occurred during load from {self.file_path}: {e}. Initializing new memory.")