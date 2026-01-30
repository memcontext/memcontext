import json
from collections import deque
from typing import Any, Dict, Optional

from .utils import get_timestamp, ensure_directory_exists


class ShortTermMemory:
    def __init__(
        self,
        file_path,
        max_capacity=10,
        storage: Optional[Any] = None,
        user_id: Optional[str] = None,
    ):
        self.max_capacity = max_capacity
        self.file_path = file_path
        self.storage = storage
        self.user_id = user_id
        ensure_directory_exists(self.file_path)
        self.memory = deque(maxlen=max_capacity)
        self.load()

    def add_qa_pair(self, qa_pair):
        qa_copy = dict(qa_pair)
        if "timestamp" not in qa_copy or not qa_copy["timestamp"]:
            qa_copy["timestamp"] = get_timestamp()
        if "meta_data" not in qa_copy or qa_copy["meta_data"] is None:
            qa_copy["meta_data"] = {}

        if self.storage is not None and self.user_id is not None:
            while getattr(self.storage, "count_short_term_items", lambda _: 0)(
                self.user_id
            ) >= self.max_capacity:
                self.storage.pop_oldest_short_term_item(self.user_id)
            self.storage.add_short_term_item(self.user_id, qa_copy)
            self.memory.append(qa_copy)
        else:
            self.memory.append(qa_copy)
            self.save()

        print(f"ShortTermMemory: Added QA. User: {qa_pair.get('user_input','')[:30]}...")

    def get_all(self):
        return list(self.memory)

    def is_full(self):
        return len(self.memory) >= self.max_capacity

    def pop_oldest(self):
        if self.storage is not None and self.user_id is not None:
            removed = self.storage.pop_oldest_short_term_item(self.user_id)
            if removed is not None:
                if self.memory:
                    self.memory.popleft()
                print("ShortTermMemory: Evicted oldest QA pair.")
                return removed
            return None
        if self.memory:
            msg = self.memory.popleft()
            print("ShortTermMemory: Evicted oldest QA pair.")
            self.save()
            return msg
        return None

    def save(self):
        if self.storage is not None and self.user_id is not None:
            return
        try:
            ensure_directory_exists(self.file_path)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(list(self.memory), f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Error saving ShortTermMemory to {self.file_path}: {e}")

    def load(self):
        if self.storage is not None and self.user_id is not None:
            try:
                items = self.storage.load_short_term_items(self.user_id)
                self.memory = deque(items, maxlen=self.max_capacity)
                print(f"ShortTermMemory: Loaded from storage for user {self.user_id}. Items: {len(self.memory)}.")
            except Exception as e:
                self.memory = deque(maxlen=self.max_capacity)
                print(f"ShortTermMemory: Error loading from storage, fallback to empty. Error: {e}")
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.memory = deque(data, maxlen=self.max_capacity)
                else:
                    self.memory = deque(maxlen=self.max_capacity)
            print(f"ShortTermMemory: Loaded from {self.file_path}.")
        except FileNotFoundError:
            self.memory = deque(maxlen=self.max_capacity)
            print(f"ShortTermMemory: No history file found at {self.file_path}. Initializing new memory.")
        except json.JSONDecodeError:
            self.memory = deque(maxlen=self.max_capacity)
            print(f"ShortTermMemory: Error decoding JSON from {self.file_path}. Initializing new memory.")
        except Exception as e:
            self.memory = deque(maxlen=self.max_capacity)
            print(f"ShortTermMemory: An unexpected error occurred during load from {self.file_path}: {e}. Initializing new memory.") 