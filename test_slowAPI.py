import requests
import time

BASE_URL = "http://127.0.0.1:5019"

# 快速发送 15 个请求
for i in range(15):
    response = requests.post(
        f"{BASE_URL}/init_memory",
        json={"user_id": f"test_{i}"}
    )
    print(f"请求 {i+1}: {response.status_code}")
    time.sleep(0.1) 