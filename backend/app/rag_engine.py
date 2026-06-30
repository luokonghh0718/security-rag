"""
安全知识库 RAG 核心引擎
- 使用 ChromaDB 存储文档向量
- 使用智谱 Embedding 模型
- 使用 DeepSeek LLM 生成回答
"""
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from .config import (
    DEEPSEEK_API_KEY,
    CHROMA_PERSIST_DIR,
    CHUNK_SIZE,
    TOP_K,
    KNOWLEDGE_FILE,
    LLM_MODEL,
)
from .embedder import ZhipuEmbedder
from .prompts import SYSTEM_PROMPT


class SecurityRAG:
    """
    网络安全 RAG 系统
    整合向量检索 + LLM 生成
    """

    def __init__(self):
        self.embedder = ZhipuEmbedder()

        # 初始化 ChromaDB（持久化模式）
        self.chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name="security_knowledge",
            embedding_function=self.embedder,  # 自定义 embedding 函数
            metadata={"description": "网络安全知识库 - NVD CVE + MITRE ATT&CK"},
        )

        # 初始化 DeepSeek 客户端
        self.llm_client = None
        if DEEPSEEK_API_KEY:
            self.llm_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
            )

        self._loaded = False

    # ── 加载知识库 ─────────────────────────────────────
    def load_knowledge(self, file_path: str = None) -> int:
        """
        从 knowledge_raw.txt 读取知识，分块向量化存入 ChromaDB

        Args:
            file_path: 知识文件路径，默认使用配置路径

        Returns:
            加载的文档块数量
        """
        path = file_path or KNOWLEDGE_FILE

        if not os.path.exists(path):
            print(f"[WARN] 知识库文件不存在: {path}")
            return 0

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 按章节分割
        chunks = self._split_into_chunks(content)

        if not chunks:
            print("[WARN] 知识库文件为空")
            return 0

        # 清除旧数据
        try:
            existing_ids = self.collection.get()["ids"]
            if existing_ids:
                self.collection.delete(ids=existing_ids)
        except Exception:
            pass

        # 批量插入
        ids = [f"doc_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": self._extract_source(chunk), "index": i}
            for i, chunk in enumerate(chunks)
        ]

        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )

        self._loaded = True
        print(f"[INFO] 知识库加载完成: {len(chunks)} 个文档块")
        return len(chunks)

    # ── 查询 ───────────────────────────────────────────
    def query(self, question: str) -> Dict:
        """
        执行 RAG 查询：检索 → 生成

        Args:
            question: 用户问题

        Returns:
            {"answer": str, "sources": List[str], "chunks": int}
        """
        # 1. 向量检索
        results = self.collection.query(
            query_texts=[question],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

        retrieved_docs = results.get("documents", [[]])[0]
        retrieved_metas = results.get("metadatas", [[]])[0]

        if not retrieved_docs:
            return {
                "answer": "抱歉，当前知识库中未包含相关信息。请尝试其他问题，或更新知识库数据。",
                "sources": [],
                "chunks": 0,
            }

        # 2. 提取来源
        sources = list(set(
            meta.get("source", "未知来源")
            for meta in retrieved_metas
            if meta and meta.get("source")
        ))

        # 3. 构建上下文
        context = "\n\n---\n\n".join(
            f"[来源 {i+1}] {doc}"
            for i, doc in enumerate(retrieved_docs)
        )

        # 4. 调用 LLM 生成
        prompt = SYSTEM_PROMPT.format(context=context, question=question)

        if self.llm_client:
            answer = self._call_llm(prompt)
        else:
            answer = self._fallback_answer(retrieved_docs)

        return {
            "answer": answer,
            "sources": sources,
            "chunks": len(retrieved_docs),
        }

    # ── 私有方法 ───────────────────────────────────────
    def _call_llm(self, prompt: str) -> str:
        """调用 DeepSeek API 生成回答"""
        try:
            response = self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] DeepSeek API 调用失败: {e}")
            return "抱歉，LLM 服务暂时不可用，请稍后重试。"

    @staticmethod
    def _fallback_answer(docs: List[str]) -> str:
        """无 LLM 时的降级回答：返回检索到的文档摘要"""
        if not docs:
            return "知识库中未找到相关信息。"

        summary_parts = []
        for i, doc in enumerate(docs[:3], 1):
            # 截取前 200 字符
            short = doc[:200] + "..." if len(doc) > 200 else doc
            summary_parts.append(f"{i}. {short}")

        return (
            "以下是与您问题相关的安全知识（当前 LLM 服务未配置，仅返回原始检索结果）：\n\n"
            + "\n\n".join(summary_parts)
        )

    @staticmethod
    def _split_into_chunks(text: str) -> List[str]:
        """
        将文本按章节和自然段落分块

        分块策略：
        1. 先按 === 分隔符识别章节
        2. 在章节内，按双换行分成段落
        3. 将段落合并到 CHUNK_SIZE 左右
        """
        # 按章节头分割
        sections = re.split(r"\n={10,}\n", text)

        chunks = []
        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 按段落分割
            paragraphs = re.split(r"\n\n+", section)

            current_chunk = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # 如果加入当前段落后超限，则保存当前块
                if len(current_chunk) + len(para) > CHUNK_SIZE and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para

            # 保存最后一块
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def _extract_source(chunk: str) -> str:
        """
        从文档块中提取来源标识

        匹配模式：
        - 【CVE-2024-XXXXX】
        - === CVE-2024-XXXXX ===
        - 漏洞ID：CVE-2024-XXXXX
        - 【ATT&CK TXXXX】
        """
        # 匹配全角括号格式：【CVE-YYYY-NNNNN】
        cve_match = re.search(r"【(CVE-\d{4}-\d+)】", chunk)
        if cve_match:
            return cve_match.group(1)

        # 匹配新格式：漏洞ID：CVE-YYYY-NNNNN
        cve_id_match = re.search(r"漏洞ID[：:]\s*(CVE-\d{4}-\d+)", chunk)
        if cve_id_match:
            return cve_id_match.group(1)

        # 匹配章节标题：=== CVE-YYYY-NNNNN ===
        cve_header_match = re.search(r"={3,}\s*(CVE-\d{4}-\d+)\s*={3,}", chunk)
        if cve_header_match:
            return cve_header_match.group(1)

        attack_match = re.search(r"【(ATT&CK T\d+)】", chunk)
        if attack_match:
            return attack_match.group(1)

        # 检查章节标题
        if "CVE" in chunk[:100] or "漏洞" in chunk[:100]:
            return "CVE漏洞数据"
        elif "ATT&CK" in chunk[:100] or "攻击技术" in chunk[:100]:
            return "ATT&CK攻击技术"
        elif "防御" in chunk[:100] or "渗透" in chunk[:100]:
            return "渗透测试防御知识"

        return "安全知识库"


# ── 全局单例 ──────────────────────────────────────────
_rag_instance: Optional[SecurityRAG] = None


def get_rag() -> SecurityRAG:
    """获取 RAG 全局单例"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SecurityRAG()
    return _rag_instance
