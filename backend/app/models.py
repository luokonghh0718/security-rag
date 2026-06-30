"""
Pydantic 数据模型
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Question(BaseModel):
    """用户问题"""
    text: str = Field(..., min_length=1, max_length=2000, description="用户输入的问题")
    top_k: Optional[int] = Field(default=None, ge=1, le=10, description="返回文档数量（覆盖默认值）")


class Source(BaseModel):
    """答案来源"""
    title: str = Field(..., description="来源标识（CVE编号/ATT&CK ID）")
    snippet: Optional[str] = Field(default=None, description="来源片段")


class Answer(BaseModel):
    """RAG 回答"""
    answer: str = Field(..., description="生成的回答")
    sources: List[str] = Field(default_factory=list, description="参考来源列表")
    chunks_count: int = Field(default=0, description="检索到的文档块数量")


class ReloadResult(BaseModel):
    """知识库重载结果"""
    success: bool
    chunks_loaded: int
    message: str


class StatusResponse(BaseModel):
    """服务状态"""
    status: str
    knowledge_loaded: bool
    api_configured: bool
    version: str = "1.0.0"


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    token: str = Field(default="", description="JWT token")
    message: str = Field(default="", description="结果描述")
