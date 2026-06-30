"""
智谱 Embedding 模型封装
使用 ZhipuAI embedding-2 模型进行文本向量化
"""
from typing import List
import httpx
from .config import ZHIPU_API_KEY, EMBEDDING_MODEL


class ZhipuEmbedder:
    """
    智谱 Embedding 函数类
    实现 ChromaDB 所需的 __call__ 接口：接收字符串列表，返回向量列表

    当 ZHIPU_API_KEY 未配置时，自动降级为简单的哈希向量（仅供开发测试）
    """

    ZHIPU_EMBEDDING_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or ZHIPU_API_KEY
        self.model = model or EMBEDDING_MODEL
        self._fallback = not bool(self.api_key)

        if self._fallback:
            print("[WARNING] ZHIPU_API_KEY 未配置，使用哈希降级向量（仅供测试）")

    def __call__(self, input_texts: List[str]) -> List[List[float]]:
        """
        ChromaDB 自定义 embedding 函数接口
        接收字符串列表，返回向量列表
        """
        if self._fallback:
            return self._hash_embed(input_texts)
        return self._api_embed(input_texts)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表（批量）"""
        return self(texts)

    def embed_query(self, text: str) -> List[float]:
        """嵌入查询文本（单条）"""
        results = self([text])
        return results[0]

    def _api_embed(self, texts: List[str]) -> List[List[float]]:
        """
        通过智谱 API 获取 embedding
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.ZHIPU_EMBEDDING_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            # 按 index 排序后提取 embedding
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in embeddings]

        except Exception as e:
            print(f"[ERROR] 智谱 Embedding API 调用失败: {e}")
            print("[INFO] 降级使用哈希向量")
            return self._hash_embed(texts)

    @staticmethod
    def _hash_embed(texts: List[str]) -> List[List[float]]:
        """
        降级方案：使用简单哈希生成固定维度向量
        维度设为 1024，与 embedding-2 一致
        """
        import hashlib

        DIM = 1024

        def _text_to_vec(t: str) -> List[float]:
            # 使用 SHA256 哈希扩展到 1024 维
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = []
            seed = int.from_bytes(h[:4], "big")
            for i in range(DIM):
                # 使用简单确定性伪随机生成
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                vec.append((seed / 0x7FFFFFFF) * 2 - 1)
            # 归一化
            norm = sum(x * x for x in vec) ** 0.5
            return [x / norm for x in vec] if norm > 0 else [0.0] * DIM

        return [_text_to_vec(t) for t in texts]
