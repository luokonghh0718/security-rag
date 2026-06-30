#!/usr/bin/env python3
"""
知识库初始化脚本
- 独立运行，触发数据获取和知识库加载
- 用于测试和手动初始化
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def main():
    print("=" * 60)
    print("  安全知识库 RAG 系统 - 知识库初始化")
    print("=" * 60)
    print()

    # ── Step 1: 获取数据 ──────────────────────────────
    print("[Step 1/3] 获取知识库数据...")
    data_file = PROJECT_ROOT / "backend" / "app" / "data" / "knowledge_raw.txt"

    if not data_file.exists() or os.getenv("FORCE_REFETCH"):
        print("  数据文件不存在或强制刷新，运行 fetch_data.py...")
        fetch_script = PROJECT_ROOT / "scripts" / "fetch_data.py"
        if fetch_script.exists():
            os.system(f'"{sys.executable}" "{fetch_script}"')
        else:
            print(f"  [ERROR] 找不到脚本: {fetch_script}")
            return 1
    else:
        print(f"  数据文件已存在: {data_file}")

    # ── Step 2: 加载到向量库 ──────────────────────────
    print()
    print("[Step 2/3] 加载知识库到 ChromaDB...")

    try:
        from backend.app.rag_engine import SecurityRAG

        rag = SecurityRAG()
        count = rag.load_knowledge(str(data_file))
        print(f"  [OK] 成功加载 {count} 个文档块到向量数据库")
    except Exception as e:
        print(f"  [ERROR] 加载失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ── Step 3: 测试查询 ──────────────────────────────
    print()
    print("[Step 3/3] 测试查询...")

    test_questions = [
        "SQL注入如何防御？",
        "最近有哪些高危漏洞？",
        "ATT&CK T1059是什么？",
    ]

    try:
        for q in test_questions:
            print(f"\n  👤 问题: {q}")
            result = rag.query(q)
            answer_preview = result["answer"][:150] + "..." if len(result["answer"]) > 150 else result["answer"]
            print(f"  🤖 回答: {answer_preview}")
            print(f"  📎 来源: {', '.join(result['sources'][:3])}")
    except Exception as e:
        print(f"  [ERROR] 查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    print("=" * 60)
    print("  ✅ 知识库初始化完成！")
    print("=" * 60)
    print()
    print("  启动服务:")
    print("    cd backend && uvicorn app.main:app --reload")
    print()
    print("  启动前端:")
    print("    cd frontend && npm install && npm run dev")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
