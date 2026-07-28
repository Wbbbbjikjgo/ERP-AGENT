"""
MCP Server 配置模块
ERP 后端地址 + MCP 监听配置
"""
import os
from dotenv import load_dotenv

# 加载项目根目录 .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Java ERP 后端地址
ERP_BASE_URL = os.getenv("ERP_BASE_URL", "http://47.92.108.163:8081")

# MCP Server 监听配置
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "9000"))

# HTTP 客户端配置
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
HTTP_MAX_CONNECTIONS = int(os.getenv("HTTP_MAX_CONNECTIONS", "20"))
