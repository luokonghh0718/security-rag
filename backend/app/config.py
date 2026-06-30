"""
安全知识库 RAG 系统配置
从 .env 文件读取环境变量，提供默认值
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# ── API 密钥 ──────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")

# ── 模型配置 ──────────────────────────────────────────
LLM_MODEL = "deepseek-chat"           # DeepSeek 对话模型
EMBEDDING_MODEL = "embedding-2"       # 智谱 embedding 模型

# ── ChromaDB 配置 ─────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    str(BASE_DIR / "data" / "chroma_db")
)
CHUNK_SIZE = 500         # 文本分块大小（字符数）
TOP_K = 3                # 检索返回的相关文档数量

# ── 数据源 URL ────────────────────────────────────────
NVD_FEED_URL = os.getenv(
    "NVD_FEED_URL",
    "https://services.nvd.nist.gov/rest/json/cves/2.0/?pubStartDate={{date}}&pubEndDate={{date}}"
)

ATTACK_STIX_URL = os.getenv(
    "ATTACK_STIX_URL",
    "https://raw.githubusercontent.com/mitre/cti/refs/heads/master/enterprise-attack/enterprise-attack.json"
)

# ── 知识库文件路径 ───────────────────────────────────
KNOWLEDGE_FILE = str(BASE_DIR / "backend" / "app" / "data" / "knowledge_raw.txt")

# ── JWT 认证配置 ───────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "security-rag-secret-key-2024")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "hwj")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "2004")

# ── 服务配置 ──────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
