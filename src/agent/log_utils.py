"""
日志工具模块
结构化日志配置，按模块分 logger
"""
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return str(log_entry)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# 预定义模块 logger
agent_logger = get_logger("agent")
mcp_logger = get_logger("mcp")
sandbox_logger = get_logger("sandbox")
web_logger = get_logger("web")
middleware_logger = get_logger("middleware")
