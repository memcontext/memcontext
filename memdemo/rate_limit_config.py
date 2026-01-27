"""
SlowAPI 限流配置
将 Redis URL 和限流规则集中管理
"""
import os
from typing import Dict, Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


class RateLimitConfig:
    """限流配置类"""
    
    # ========================
    # Redis 配置
    # ========================
    # Redis URL，支持以下格式：
    # - redis://localhost:6379
    # - redis://:password@localhost:6379
    # - redis://localhost:6379/0  (指定数据库)
    REDIS_URL: str = os.environ.get(
        'REDIS_URL',
        'redis://localhost:6379'  # 默认值
    )
    
    # Redis 连接池配置（可选）
    REDIS_MAX_CONNECTIONS: int = int(os.environ.get('REDIS_MAX_CONNECTIONS', '50'))
    REDIS_SOCKET_TIMEOUT: int = int(os.environ.get('REDIS_SOCKET_TIMEOUT', '5'))
    REDIS_SOCKET_CONNECT_TIMEOUT: int = int(os.environ.get('REDIS_SOCKET_CONNECT_TIMEOUT', '5'))
    
    # ========================
    # 全局限流规则（默认）
    # ========================
    # 格式："{数量}/{时间单位}"
    # 例如："100/minute" 表示每分钟 100 次
    # 支持的单位：second, minute, hour, day
    DEFAULT_RATE_LIMIT: str = os.environ.get(
        'DEFAULT_RATE_LIMIT',
        '100/minute'  # 默认：每分钟 100 次请求
    )
    
    # ========================
    # 各接口的限流规则
    # ========================
    # 可以为不同的接口设置不同的限流规则
    # 如果接口不在这个字典中，将使用 DEFAULT_RATE_LIMIT
    ROUTE_LIMITS: Dict[str, str] = {
        
        '/init_memory': '10/minute',
        
        # 聊天接口 - 允许较频繁的请求
        '/chat': '10/minute',
        
        # 文件上传接口 - 限制较严格，防止资源滥用
        '/add_multimodal_memory': '30/hour',
        '/add_multimodal_memory_stream': '30/hour',
        
        # 导入接口 - 限制较严格
        '/import_from_cache': '30/hour',
        '/import_conversations': '30/hour',
        
        # 查询接口 - 允许较频繁的查询
        '/memory_state': '120/minute',  # 前端会频繁轮询
        
        # 分析接口 - 限制较严格，因为计算成本高
        '/trigger_analysis': '4/minute',
        '/personality_analysis': '3/minute',
        
        # 清空接口 - 非常严格，防止误操作
        '/clear_memory': '5/hour',
    }
    
    # ========================
    # 限流键函数配置
    # ========================
    # 可选值：
    # - 'ip': 按 IP 地址限流（默认）
    # - 'user': 按用户 ID 限流（需要自定义 key_func）
    # - 'global': 全局限流（所有用户共享）
    KEY_FUNC_TYPE: str = os.environ.get('RATE_LIMIT_KEY_FUNC', 'ip')
    
    # ========================
    # 限流响应配置
    # ========================
    # 当触发限流时，是否返回详细信息
    INCLUDE_HEADERS: bool = True  # 在响应头中包含限流信息
    
    # 限流错误消息
    RATE_LIMIT_MESSAGE: str = "Rate limit exceeded. Please try again later."
    
    # ========================
    # 辅助方法
    # ========================
    @classmethod
    def get_route_limit(cls, route_path: str) -> str:
        """
        获取指定路由的限流规则
        
        Args:
            route_path: 路由路径，例如 '/chat'
            
        Returns:
            限流规则字符串，例如 '60/minute'
        """
        return cls.ROUTE_LIMITS.get(route_path, cls.DEFAULT_RATE_LIMIT)
    
    @classmethod
    def get_redis_config(cls) -> Dict[str, any]:
        """
        获取 Redis 配置字典
        
        Returns:
            Redis 配置字典
        """
        return {
            'url': cls.REDIS_URL,
            'max_connections': cls.REDIS_MAX_CONNECTIONS,
            'socket_timeout': cls.REDIS_SOCKET_TIMEOUT,
            'socket_connect_timeout': cls.REDIS_SOCKET_CONNECT_TIMEOUT,
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """
        验证配置是否有效
        
        Returns:
            True 如果配置有效，否则 False
        """
        # 验证 Redis URL 格式
        if not cls.REDIS_URL.startswith('redis://'):
            print(f"警告: Redis URL 格式可能不正确: {cls.REDIS_URL}")
            return False
        
        # 验证限流规则格式
        for route, limit in cls.ROUTE_LIMITS.items():
            if not cls._validate_limit_format(limit):
                print(f"警告: 限流规则格式不正确 [{route}]: {limit}")
                return False
        
        return True
    
    @staticmethod
    def _validate_limit_format(limit: str) -> bool:
        """
        验证限流规则格式
        
        Args:
            limit: 限流规则字符串，例如 '60/minute'
            
        Returns:
            True 如果格式正确，否则 False
        """
        try:
            parts = limit.split('/')
            if len(parts) != 2:
                return False
            count = int(parts[0])
            unit = parts[1].lower()
            valid_units = ['second', 'minute', 'hour', 'day']
            return unit in valid_units and count > 0
        except (ValueError, AttributeError):
            return False


# 导出配置实例
config = RateLimitConfig()

# 启动时验证配置
if __name__ == '__main__':
    if config.validate_config():
        print("✓ 限流配置验证通过")
        print(f"  Redis URL: {config.REDIS_URL}")
        print(f"  默认限流: {config.DEFAULT_RATE_LIMIT}")
        print(f"  路由限流规则数量: {len(config.ROUTE_LIMITS)}")
    else:
        print("✗ 限流配置验证失败，请检查配置")
