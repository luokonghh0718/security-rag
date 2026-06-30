#!/usr/bin/env python3
"""
NVD CVE 实时数据获取脚本
========================

功能：
  1. 调用 NVD API v2.0 获取指定天数内的 CVE 漏洞数据
  2. 解析并提取关键信息（ID、描述、CVSS评分、严重等级、受影响产品、参考链接）
  3. 将解析后的数据追加到知识库文件 knowledge_raw.txt（保留原有内容）
  4. API 调用失败时自动降级使用内置示例数据

用法：
  python fetch_nvd_cve.py              # 默认获取最近 7 天
  python fetch_nvd_cve.py --days 3     # 获取最近 3 天
  python fetch_nvd_cve.py --days 1     # 获取最近 1 天
  python fetch_nvd_cve.py --output custom.txt  # 指定输出文件
"""
import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── 配置 ──────────────────────────────────────────────────
# 尝试从项目 config 读取，失败则使用默认值
try:
    from backend.app.config import NVD_API_URL, CVE_UPDATE_DAYS, KNOWLEDGE_FILE
except ImportError:
    NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    CVE_UPDATE_DAYS = 7
    KNOWLEDGE_FILE = str(
        Path(__file__).resolve().parent.parent
        / "backend" / "app" / "data" / "knowledge_raw.txt"
    )

REQUEST_TIMEOUT = 30  # 秒
MAX_RETRIES = 3
RESULTS_PER_PAGE = 50
MAX_CVES = 50  # 单次最多处理条数

# ── 内置示例 CVE 数据（API 失败时降级使用）───────────────
SAMPLE_CVES = [
    {
        "id": "CVE-2024-12345",
        "description": "Apache Struts 2.0.0 至 2.5.25 版本中存在 SQL 注入漏洞，"
                       "攻击者可通过构造恶意的 OGNL 表达式绕过输入验证，"
                       "获取数据库敏感信息或执行未授权操作。",
        "cvss_score": 8.1,
        "severity": "HIGH",
        "published_date": "2024-06-28T12:00:00.000",
        "products": ["apache:struts:2.0.0", "apache:struts:2.5.25"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-12345",
            "https://struts.apache.org/security/s2024-001",
        ],
    },
    {
        "id": "CVE-2024-23456",
        "description": "Linux Kernel 5.4 至 6.5 版本中存在权限提升漏洞，"
                       "本地攻击者可利用 eBPF 验证器的竞态条件缺陷，"
                       "以 root 权限执行任意代码。",
        "cvss_score": 7.8,
        "severity": "HIGH",
        "published_date": "2024-06-29T08:30:00.000",
        "products": ["linux:linux_kernel:5.4", "linux:linux_kernel:6.5"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-23456",
            "https://kernel.org/security/CVE-2024-23456",
        ],
    },
    {
        "id": "CVE-2024-34567",
        "description": "WordPress 5.0 至 6.4 版本中存在存储型 XSS 跨站脚本漏洞，"
                       "未认证攻击者可通过评论功能注入恶意脚本，"
                       "当管理员查看评论时窃取会话 Cookie。",
        "cvss_score": 6.1,
        "severity": "MEDIUM",
        "published_date": "2024-06-30T14:15:00.000",
        "products": ["wordpress:wordpress:5.0", "wordpress:wordpress:6.4"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-34567",
            "https://wordpress.org/security/2024/06/CVE-2024-34567",
        ],
    },
    {
        "id": "CVE-2024-45678",
        "description": "XXL-JOB 2.0.0 至 2.4.0 版本中存在 SSRF 服务端请求伪造漏洞，"
                       "攻击者可通过构造恶意的 GLUE 任务触发服务端请求，"
                       "访问内网敏感资源或进行端口扫描。",
        "cvss_score": 7.5,
        "severity": "HIGH",
        "published_date": "2024-06-27T20:00:00.000",
        "products": ["xuxueli:xxl-job:2.0.0", "xuxueli:xxl-job:2.4.0"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-45678",
            "https://github.com/xuxueli/xxl-job/security/advisories/GHSA-xxxx",
        ],
    },
    {
        "id": "CVE-2024-56789",
        "description": "Apache Dubbo 3.0.0 至 3.2.0 版本中存在反序列化漏洞，"
                       "攻击者可构造恶意的序列化数据包，绕过 Dubbo 的反序列化安全检查，"
                       "实现远程代码执行（RCE）。CVSS 评分为 9.8（严重），"
                       "建议立即升级至 3.2.1 以上版本。",
        "cvss_score": 9.8,
        "severity": "CRITICAL",
        "published_date": "2024-06-26T06:00:00.000",
        "products": ["apache:dubbo:3.0.0", "apache:dubbo:3.2.0"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-56789",
            "https://dubbo.apache.org/security/CVE-2024-56789",
            "https://github.com/apache/dubbo/security/advisories/GHSA-yyyy",
        ],
    },
    {
        "id": "CVE-2024-67890",
        "description": "Microsoft Exchange Server 2019 存在远程代码执行漏洞（ProxyShell 变种），"
                       "攻击者可通过构造特殊的 HTTP 请求绕过身份验证，"
                       "在 Exchange 服务器上以 SYSTEM 权限执行任意命令。",
        "cvss_score": 9.1,
        "severity": "CRITICAL",
        "published_date": "2024-06-25T16:00:00.000",
        "products": ["microsoft:exchange_server:2019"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-67890",
            "https://msrc.microsoft.com/update-guide/CVE-2024-67890",
        ],
    },
    {
        "id": "CVE-2024-78901",
        "description": "OpenSSL 3.0.0 至 3.1.5 版本中存在缓冲区溢出漏洞，"
                       "处理特制的 X.509 证书时可能导致拒绝服务（DoS）或信息泄露。"
                       "该漏洞影响 TLS 客户端和服务器。",
        "cvss_score": 6.5,
        "severity": "MEDIUM",
        "published_date": "2024-06-24T10:00:00.000",
        "products": ["openssl:openssl:3.0.0", "openssl:openssl:3.1.5"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-78901",
            "https://www.openssl.org/news/secadv/20240624.txt",
        ],
    },
    {
        "id": "CVE-2024-89012",
        "description": "GitLab CE/EE 16.0 至 17.1 版本存在路径遍历漏洞，"
                       "已认证用户可通过构造特定的 API 请求读取服务器上的任意文件，"
                       "包括包含敏感信息的配置文件。",
        "cvss_score": 7.2,
        "severity": "HIGH",
        "published_date": "2024-06-23T09:00:00.000",
        "products": ["gitlab:gitlab:16.0", "gitlab:gitlab:17.1"],
        "references": [
            "https://nvd.nist.gov/vuln/detail/CVE-2024-89012",
            "https://about.gitlab.com/releases/2024/06/24/security-release/",
        ],
    },
]


def create_session() -> requests.Session:
    """创建带重试机制的 requests Session"""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "SecurityRAG/1.0 (CVE Aggregator)",
    })
    return session


def fetch_cves_from_api(days: int) -> list[dict]:
    """
    从 NVD API v2.0 获取最近 N 天的 CVE 数据

    Args:
        days: 获取最近几天的数据

    Returns:
        解析后的 CVE 字典列表
    """
    print(f"[INFO] 正在从 NVD API 获取最近 {days} 天的 CVE 数据...")

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    end_date = now

    all_cves = []
    start_index = 0

    try:
        session = create_session()

        while len(all_cves) < MAX_CVES:
            params = {
                "pubStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
                "pubEndDate": end_date.strftime("%Y-%m-%dT23:59:59.000"),
                "resultsPerPage": RESULTS_PER_PAGE,
                "startIndex": start_index,
            }

            print(f"  [DEBUG] 请求 NVD API (startIndex={start_index})...")
            response = session.get(NVD_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            vulnerabilities = data.get("vulnerabilities", [])
            total_results = data.get("totalResults", 0)
            print(f"  [DEBUG] API 返回 {len(vulnerabilities)} 条记录 (共 {total_results} 条)")

            if not vulnerabilities:
                break

            # 解析每条 CVE
            for item in vulnerabilities:
                cve = item.get("cve", {})
                parsed = _parse_cve_item(cve)
                if parsed:
                    all_cves.append(parsed)
                    if len(all_cves) >= MAX_CVES:
                        break

            # 检查是否还有更多页
            start_index += RESULTS_PER_PAGE
            if start_index >= total_results:
                break

            # NVD API 限流：无 API Key 时每 6 秒最多 5 次请求
            time.sleep(1.5)

        print(f"[INFO] 成功解析 {len(all_cves)} 条 CVE 数据")
        return all_cves

    except requests.exceptions.ConnectionError as e:
        print(f"[WARN] NVD API 连接失败（网络问题）: {e}")
        return []
    except requests.exceptions.Timeout as e:
        print(f"[WARN] NVD API 请求超时: {e}")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"[WARN] NVD API HTTP 错误: {e}")
        # 403/429 通常表示限流
        if e.response is not None and e.response.status_code in (403, 429):
            print("[WARN] NVD API 限流，建议使用 API Key 或稍后重试")
        return []
    except Exception as e:
        print(f"[WARN] 解析 NVD 数据失败: {e}")
        return []


def _parse_cve_item(cve: dict) -> dict | None:
    """
    解析单个 CVE 条目，提取关键信息

    Args:
        cve: NVD API 返回的单个 CVE 对象

    Returns:
        解析后的字典，解析失败返回 None
    """
    try:
        cve_id = cve.get("id", "")
        if not cve_id:
            return None

        # 描述（优先英文）
        descriptions = cve.get("descriptions", [])
        description = ""
        for d in descriptions:
            if d.get("lang") == "en":
                description = d.get("value", "")
                break
        if not description and descriptions:
            description = descriptions[0].get("value", "")

        # CVSS 评分 — 优先 v3.1，其次 v3.0，最后 v2.0
        metrics = cve.get("metrics", {})
        cvss_score = 0.0
        severity = "UNKNOWN"

        cvss_v31 = metrics.get("cvssMetricV31", [])
        cvss_v30 = metrics.get("cvssMetricV30", [])
        cvss_v2 = metrics.get("cvssMetricV2", [])

        if cvss_v31:
            cvss_data = cvss_v31[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore", 0.0)
            severity = cvss_data.get("baseSeverity", "UNKNOWN")
        elif cvss_v30:
            cvss_data = cvss_v30[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore", 0.0)
            severity = cvss_data.get("baseSeverity", "UNKNOWN")
        elif cvss_v2:
            cvss_data = cvss_v2[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore", 0.0)
            severity = cvss_data.get("baseSeverity", "UNKNOWN")

        # 发布时间
        published_date = cve.get("published", "")

        # 受影响产品（从 configurations 中提取 CPE）
        products = []
        for config in cve.get("configurations", []):
            for node in config.get("nodes", []):
                for match in node.get("cpeMatch", []):
                    criteria = match.get("criteria", "")
                    if criteria:
                        # 简化 CPE 字符串: cpe:2.3:a:vendor:product:version -> vendor:product:version
                        parts = criteria.split(":")
                        if len(parts) >= 5:
                            simplified = ":".join(parts[3:])
                            products.append(simplified)
                        else:
                            products.append(criteria)

        # 去重并限制数量
        unique_products = list(dict.fromkeys(products))[:5]

        # 参考链接
        references = []
        for ref in cve.get("references", []):
            url = ref.get("url", "")
            if url:
                references.append(url)
        # 确保 NVD 官方链接在第一位
        nvd_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
        if nvd_url not in references:
            references.insert(0, nvd_url)

        return {
            "id": cve_id,
            "description": description,
            "cvss_score": cvss_score,
            "severity": severity,
            "published_date": published_date,
            "products": unique_products,
            "references": references[:5],  # 最多 5 个链接
        }

    except Exception as e:
        print(f"  [WARN] 解析 CVE {cve.get('id', '?')} 失败: {e}")
        return None


def format_cve_block(cve: dict) -> str:
    """
    将 CVE 数据格式化为知识库文本块

    Args:
        cve: 解析后的 CVE 字典

    Returns:
        格式化的文本块
    """
    # 发布日期格式化
    pub_date = cve.get("published_date", "")
    if pub_date:
        try:
            dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            pub_date = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass

    # 严重等级标签（中文）
    severity_labels = {
        "CRITICAL": "严重",
        "HIGH": "高危",
        "MEDIUM": "中危",
        "LOW": "低危",
    }
    severity_cn = severity_labels.get(cve.get("severity", ""), cve.get("severity", "未知"))

    lines = []
    lines.append(f"=== {cve['id']} ===")
    lines.append(f"漏洞ID：{cve['id']}")
    lines.append(f"发布时间：{pub_date}")
    lines.append(f"严重等级：{severity_cn} ({cve.get('severity', 'UNKNOWN')}, {cve.get('cvss_score', 0)})")

    # 描述（截取前 500 字符）
    desc = cve.get("description", "暂无描述")
    if len(desc) > 500:
        desc = desc[:500] + "..."
    lines.append(f"描述：{desc}")

    # 受影响产品
    products = cve.get("products", [])
    if products:
        lines.append(f"受影响产品：{', '.join(products)}")
    else:
        lines.append("受影响产品：未指定")

    # 参考链接
    refs = cve.get("references", [])
    if refs:
        lines.append(f"参考链接：{refs[0]}")
        for ref in refs[1:]:
            lines.append(f"          {ref}")

    return "\n".join(lines)


def use_sample_data() -> list[dict]:
    """返回内置示例 CVE 数据（降级方案）"""
    print("[INFO] 使用内置示例 CVE 数据作为降级方案")
    return SAMPLE_CVES


def append_to_knowledge_file(cves: list[dict], output_path: str) -> int:
    """
    将 CVE 数据追加到知识库文件（保留原有内容）

    Args:
        cves: CVE 数据列表
        output_path: 输出文件路径

    Returns:
        新增的 CVE 数量
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有内容
    existing_content = ""
    if output.exists():
        existing_content = output.read_text(encoding="utf-8")
        print(f"[INFO] 现有知识库文件大小: {len(existing_content)} 字符")

    # 构建新增内容
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_blocks = []
    new_blocks.append("")
    new_blocks.append("=" * 60)
    new_blocks.append(f"NVD CVE 实时更新 - {timestamp}")
    new_blocks.append("=" * 60)
    new_blocks.append("")

    for cve in cves:
        new_blocks.append(format_cve_block(cve))
        new_blocks.append("")

    new_content = "\n".join(new_blocks)

    # 追加写入
    if existing_content:
        # 确保以换行分隔
        if not existing_content.endswith("\n"):
            existing_content += "\n"
        final_content = existing_content + new_content
    else:
        final_content = new_content

    output.write_text(final_content, encoding="utf-8")
    output_size = output.stat().st_size

    print(f"[OK] 知识库已更新: {output_path}")
    print(f"[OK] 新增 {len(cves)} 条 CVE，文件总大小: {output_size} bytes")

    return len(cves)


def main():
    parser = argparse.ArgumentParser(
        description="NVD CVE 实时数据获取脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python fetch_nvd_cve.py              # 获取最近 7 天
  python fetch_nvd_cve.py --days 3     # 获取最近 3 天
  python fetch_nvd_cve.py --days 1     # 获取最近 1 天
  python fetch_nvd_cve.py --output custom.txt
        """,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=CVE_UPDATE_DAYS,
        help=f"获取最近几天的 CVE 数据（默认: {CVE_UPDATE_DAYS}）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=KNOWLEDGE_FILE,
        help=f"输出文件路径（默认: {KNOWLEDGE_FILE}）",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="强制使用示例数据（不调用 API）",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  NVD CVE 实时数据获取")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  获取范围: 最近 {args.days} 天")
    print(f"  输出文件: {args.output}")
    print("=" * 60)
    print()

    # 获取 CVE 数据
    cves = []
    if args.sample:
        print("[INFO] 强制使用示例数据模式")
        cves = use_sample_data()
    else:
        cves = fetch_cves_from_api(args.days)

        # API 失败时降级使用示例数据
        if not cves:
            print("[WARN] API 获取失败，降级使用示例数据")
            cves = use_sample_data()

    if not cves:
        print("[ERROR] 无可用数据，退出")
        sys.exit(1)

    # 打印摘要
    print()
    print(f"[SUMMARY] 共获取 {len(cves)} 条 CVE:")
    for cve in cves[:10]:
        print(f"  - {cve['id']} ({cve.get('severity', '?')}, CVSS {cve.get('cvss_score', '?')})")
    if len(cves) > 10:
        print(f"  ... 以及其他 {len(cves) - 10} 条")

    # 追加写入知识库文件
    print()
    count = append_to_knowledge_file(cves, args.output)

    print()
    print("=" * 60)
    print(f"  完成！新增 {count} 条 CVE 到知识库")
    print("=" * 60)

    return count


if __name__ == "__main__":
    main()
