"""
安全知识库 RAG 系统 - FastAPI 主服务
"""
import os
import jwt
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import (
    DEEPSEEK_API_KEY, KNOWLEDGE_FILE, HOST, PORT,
    JWT_SECRET, JWT_EXPIRY_HOURS, ADMIN_USERNAME, ADMIN_PASSWORD,
)
from .models import (
    Question, Answer, ReloadResult, StatusResponse,
    LoginRequest, LoginResponse,
)
from .rag_engine import get_rag


# ── 应用生命周期 ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化知识库"""
    print("[INFO] 正在启动安全知识库 RAG 系统...")
    rag = get_rag()

    # 检查知识文件是否存在
    if os.path.exists(KNOWLEDGE_FILE):
        count = rag.load_knowledge()
        print(f"[INFO] 知识库初始化完成: {count} 个文档块")
    else:
        print(f"[WARN] 知识库文件不存在: {KNOWLEDGE_FILE}")
        print("[INFO] 请先运行 scripts/fetch_data.py 获取数据")

    yield  # 应用运行中

    print("[INFO] 安全知识库 RAG 系统正在关闭...")


# ── 创建应用 ───────────────────────────────────────────
app = FastAPI(
    title="安全知识库 RAG 系统",
    description="基于 NVD CVE 和 MITRE ATT&CK 的网络安全知识问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS 配置 ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── JWT 认证中间件 ────────────────────────────────────
PUBLIC_PATHS = {"/api/auth/login", "/docs", "/openapi.json", "/"}


@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    """JWT 认证中间件：验证 /api/* 路径的 token"""
    path = request.url.path

    # 公开路径跳过验证
    if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # OPTIONS 预检请求跳过验证
    if request.method == "OPTIONS":
        return await call_next(request)

    # 获取 Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "未提供认证令牌，请先登录"},
        )

    token = auth_header[7:]  # 去掉 "Bearer " 前缀

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        # 将用户信息注入请求（可选，后续可用）
        request.state.username = payload.get("username", "")
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"detail": "令牌已过期，请重新登录"},
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            status_code=401,
            content={"detail": "无效的认证令牌"},
        )

    return await call_next(request)


# ── API 路由 ───────────────────────────────────────────
@app.get("/", response_model=StatusResponse)
async def root():
    """返回服务状态"""
    rag = get_rag()
    return StatusResponse(
        status="running",
        knowledge_loaded=rag._loaded,
        api_configured=bool(DEEPSEEK_API_KEY),
    )


@app.post("/api/query", response_model=Answer)
async def query_question(q: Question):
    """
    查询安全知识库

    接收用户问题，返回：
    - answer: 基于知识库生成的回答
    - sources: 参考来源（CVE编号/ATT&CK ID）
    - chunks_count: 检索到的文档块数量
    """
    rag = get_rag()

    if not rag._loaded:
        raise HTTPException(
            status_code=503,
            detail="知识库尚未加载。请先运行 scripts/fetch_data.py 获取数据，"
                   "然后访问 POST /api/reload 加载知识库。",
        )

    try:
        result = rag.query(q.text)
        return Answer(
            answer=result["answer"],
            sources=result["sources"],
            chunks_count=result["chunks"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.post("/api/reload", response_model=ReloadResult)
async def reload_knowledge():
    """手动重新加载知识库"""
    rag = get_rag()

    if not os.path.exists(KNOWLEDGE_FILE):
        return ReloadResult(
            success=False,
            chunks_loaded=0,
            message=f"知识库文件不存在: {KNOWLEDGE_FILE}。请先运行 scripts/fetch_data.py",
        )

    try:
        count = rag.load_knowledge()
        return ReloadResult(
            success=True,
            chunks_loaded=count,
            message=f"知识库重载成功，共加载 {count} 个文档块",
        )
    except Exception as e:
        return ReloadResult(
            success=False,
            chunks_loaded=0,
            message=f"重载失败: {str(e)}",
        )


@app.get("/api/sources")
async def list_sources():
    """列出知识库中的所有来源"""
    rag = get_rag()
    if not rag._loaded:
        return {"sources": [], "count": 0}

    try:
        results = rag.collection.get(include=["metadatas"])
        sources = list(set(
            m.get("source", "未知")
            for m in results.get("metadatas", [])
            if m and m.get("source")
        ))
        return {"sources": sorted(sources), "count": len(sources)}
    except Exception:
        return {"sources": [], "count": 0}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """
    用户登录：验证用户名密码，返回 JWT token

    Args:
        login_data: { username, password }

    Returns:
        { success, token, message }
    """
    if login_data.username != ADMIN_USERNAME or login_data.password != ADMIN_PASSWORD:
        return LoginResponse(
            success=False,
            token="",
            message="用户名或密码错误",
        )

    # 生成 JWT token
    expiry = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "username": login_data.username,
        "exp": expiry,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return LoginResponse(
        success=True,
        token=token,
        message="登录成功",
    )


# ── 启动入口 ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
