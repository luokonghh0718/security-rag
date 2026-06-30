#!/usr/bin/env python3
"""
安全知识库数据获取脚本
功能：
  1. 从 NVD API 获取最近 7 天的 CVE 漏洞数据
  2. 从 MITRE CTI GitHub 仓库获取 ATT&CK 攻击技术数据
  3. 将数据解析为纯文本段落，保存到 knowledge_raw.txt

降级处理：当网络不可达时，使用内置示例数据
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── 配置 ──────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "data"
OUTPUT_FILE = OUTPUT_DIR / "knowledge_raw.txt"

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0/"
ATTACK_STIX_URL = "https://raw.githubusercontent.com/mitre/cti/refs/heads/master/enterprise-attack/enterprise-attack.json"

REQUEST_TIMEOUT = 30  # 秒
MAX_RETRIES = 2

# ── 示例数据（网络失败时降级使用）─────────────────────
SAMPLE_CVE_DATA = [
    {
        "id": "CVE-2024-12345",
        "description": "某Web应用存在SQL注入漏洞，攻击者可通过构造恶意参数获取数据库敏感信息。",
        "cvss": 8.1,
        "severity": "高危",
        "product": "Apache Struts 2.0.0-2.5.25"
    },
    {
        "id": "CVE-2024-23456",
        "description": "某操作系统内核存在权限提升漏洞，本地攻击者可利用该漏洞获取root权限。",
        "cvss": 7.8,
        "severity": "高危",
        "product": "Linux Kernel 5.4-6.5"
    },
    {
        "id": "CVE-2024-34567",
        "description": "某流行CMS存在XSS跨站脚本漏洞，攻击者可注入恶意脚本窃取用户Cookie。",
        "cvss": 6.1,
        "severity": "中危",
        "product": "WordPress 5.0-6.4"
    },
    {
        "id": "CVE-2024-45678",
        "description": "某企业级应用存在SSRF服务端请求伪造漏洞，攻击者可利用该漏洞访问内网敏感资源。",
        "cvss": 7.5,
        "severity": "高危",
        "product": "XXL-JOB 2.0.0-2.4.0"
    },
    {
        "id": "CVE-2024-56789",
        "description": "某开源框架存在反序列化漏洞，攻击者可构造恶意数据包实现远程代码执行。",
        "cvss": 9.8,
        "severity": "严重",
        "product": "Apache Dubbo 3.0.0-3.2.0"
    },
]

SAMPLE_ATTACK_DATA = [
    {"id": "T1059", "name": "Command and Scripting Interpreter",
     "description": "攻击者可能滥用命令和脚本解释器来执行命令、编写或执行脚本。这些解释器包括cmd、PowerShell、Python等。"},
    {"id": "T1078", "name": "Valid Accounts",
     "description": "攻击者可能获取和使用合法账户的凭据，以进行初始访问、持久化、权限提升或防御规避。"},
    {"id": "T1046", "name": "Network Service Scanning",
     "description": "攻击者可能扫描网络以发现可利用的服务和开放端口，为后续攻击做准备。"},
    {"id": "T1190", "name": "Exploit Public-Facing Application",
     "description": "攻击者可能利用面向公众的应用程序中的漏洞，通过互联网进行初始访问。"},
    {"id": "T1068", "name": "Exploitation for Privilege Escalation",
     "description": "攻击者可能利用软件漏洞来提升权限，可能使用导致权限提升的本地漏洞。"},
    {"id": "T1040", "name": "Network Sniffing",
     "description": "攻击者可能捕获网络流量以收集凭证或敏感信息。"},
]

SAMPLE_PENTEST_KNOWLEDGE = [
    "SQL注入防御：使用参数化查询（PreparedStatement）、输入验证与过滤、最小权限原则、使用ORM框架。",
    "XSS防御：输出编码（HTML实体编码）、CSP策略、HttpOnly Cookie、输入过滤。",
    "CSRF防御：CSRF Token、SameSite Cookie属性、验证Referer头、二次验证（如验证码）。",
    "文件上传防御：白名单校验后缀名、重命名文件、限制上传目录执行权限、使用文件内容检测。",
    "SSRF防御：白名单限制目标地址、过滤内网IP段、禁用不必要的协议。",
    "反序列化漏洞防御：不反序列化不可信数据、使用安全组件、对序列化数据进行签名校验。",
    "Linux安全加固：禁用root远程登录、修改SSH默认端口、配置防火墙只开放必要端口、定期更新系统补丁。",
    "Docker安全最佳实践：不使用root用户运行容器、最小化镜像大小、限制容器资源、定期扫描镜像漏洞。",
]


def create_session() -> requests.Session:
    """创建带重试机制的 requests Session"""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_nvd_recent() -> str:
    """
    从 NVD API 获取最近 7 天的 CVE 漏洞数据
    返回格式化的纯文本段落
    """
    print("[INFO] 正在从 NVD API 获取 CVE 数据...")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    date_str = f"{start_date.strftime('%Y-%m-%dT%H:%M:%S.000')}/{end_date.strftime('%Y-%m-%dT%H:%M:%S.000')}"

    try:
        session = create_session()
        params = {
            "pubStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
            "pubEndDate": end_date.strftime("%Y-%m-%dT23:59:59.000"),
            "resultsPerPage": 50,
        }
        response = session.get(NVD_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        vulnerabilities = data.get("vulnerabilities", [])
        if not vulnerabilities:
            print("[WARN] NVD API 返回 0 条最近漏洞记录")
            return ""

        lines = []
        for item in vulnerabilities[:30]:  # 最多取30条
            cve = item.get("cve", {})
            cve_id = cve.get("id", "UNKNOWN")

            # 描述
            descriptions = cve.get("descriptions", [])
            desc_en = ""
            for d in descriptions:
                if d.get("lang") == "en":
                    desc_en = d.get("value", "")
                    break

            # CVSS 评分
            metrics = cve.get("metrics", {})
            cvss_v31 = metrics.get("cvssMetricV31", []) or metrics.get("cvssMetricV30", [])
            cvss_score = cvss_v31[0]["cvssData"]["baseScore"] if cvss_v31 else 0.0
            severity = cvss_v31[0]["cvssData"]["baseSeverity"] if cvss_v31 else "UNKNOWN"

            # 受影响产品
            products = []
            for node in cve.get("configurations", []):
                for cpe in node.get("nodes", []):
                    for match in cpe.get("cpeMatch", []):
                        crit = match.get("criteria", "")
                        if crit:
                            products.append(crit.replace("cpe:2.3:", ""))

            product_str = ", ".join(products[:3]) if products else "未指定"

            desc_cn = desc_en[:200]  # 截取描述
            lines.append(
                f"【{cve_id}】漏洞描述：{desc_cn}。"
                f"CVSS评分：{cvss_score}（{severity}）。"
                f"受影响产品：{product_str}"
            )

        print(f"[INFO] 成功获取 {len(lines)} 条 CVE 数据")
        return "\n\n".join(lines)

    except requests.exceptions.RequestException as e:
        print(f"[WARN] NVD API 请求失败: {e}")
        return ""
    except Exception as e:
        print(f"[WARN] 解析 NVD 数据失败: {e}")
        return ""


def fetch_attack_techniques() -> str:
    """
    从 MITRE CTI GitHub 仓库获取 ATT&CK 攻击技术数据
    返回格式化的纯文本段落
    """
    print("[INFO] 正在从 MITRE CTI 获取 ATT&CK 数据...")

    try:
        session = create_session()
        response = session.get(ATTACK_STIX_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        objects = data.get("objects", [])
        techniques = [obj for obj in objects if obj.get("type") == "attack-pattern"]

        if not techniques:
            print("[WARN] ATT&CK STIX 数据中未找到攻击技术")
            return ""

        lines = []
        for tech in techniques[:20]:  # 最多取20条
            external_refs = tech.get("external_references", [])
            attack_id = ""
            for ref in external_refs:
                if ref.get("source_name") == "mitre-attack":
                    attack_id = ref.get("external_id", "")
                    break

            name = tech.get("name", "Unknown")
            description = tech.get("description", "")

            # 截取描述前 300 字符
            desc_short = description[:300].replace("\n", " ") if description else "无描述"

            lines.append(
                f"【ATT&CK {attack_id}】技术名称：{name}。"
                f"描述：{desc_short}"
            )

        print(f"[INFO] 成功获取 {len(lines)} 条 ATT&CK 技术数据")
        return "\n\n".join(lines)

    except requests.exceptions.RequestException as e:
        print(f"[WARN] MITRE CTI 请求失败: {e}")
        return ""
    except Exception as e:
        print(f"[WARN] 解析 ATT&CK 数据失败: {e}")
        return ""


def build_fallback_content() -> str:
    """使用内置示例数据构建完整知识库内容"""
    print("[INFO] 使用内置示例数据构建知识库...")

    sections = []

    # CVE 漏洞数据
    sections.append("=" * 60)
    sections.append("CVE 漏洞数据")
    sections.append("=" * 60)

    for cve in SAMPLE_CVE_DATA:
        sections.append(
            f"【{cve['id']}】漏洞描述：{cve['description']}。"
            f"CVSS评分：{cve['cvss']}（{cve['severity']}）。"
            f"受影响产品：{cve['product']}"
        )

    sections.append("")

    # ATT&CK 攻击技术
    sections.append("=" * 60)
    sections.append("ATT&CK 攻击技术")
    sections.append("=" * 60)

    for tech in SAMPLE_ATTACK_DATA:
        sections.append(
            f"【ATT&CK {tech['id']}】技术名称：{tech['name']}。"
            f"描述：{tech['description']}"
        )

    sections.append("")

    # 渗透测试知识
    sections.append("=" * 60)
    sections.append("渗透测试防御知识")
    sections.append("=" * 60)

    for item in SAMPLE_PENTEST_KNOWLEDGE:
        sections.append(item)

    return "\n".join(sections)


def main():
    print("=" * 60)
    print("  网络安全知识库 - 数据获取脚本")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 尝试获取远程数据
    cve_text = fetch_nvd_recent()
    attack_text = fetch_attack_techniques()

    has_remote_data = bool(cve_text or attack_text)

    if has_remote_data:
        # 合并远程数据写入
        print()
        print("[INFO] 写入远程获取的数据...")
        content_parts = []

        if cve_text:
            content_parts.append("=" * 60)
            content_parts.append("CVE 漏洞数据（来自 NVD API）")
            content_parts.append("=" * 60)
            content_parts.append("")
            content_parts.append(cve_text)
            content_parts.append("")

        if attack_text:
            content_parts.append("=" * 60)
            content_parts.append("ATT&CK 攻击技术（来自 MITRE CTI）")
            content_parts.append("=" * 60)
            content_parts.append("")
            content_parts.append(attack_text)
            content_parts.append("")

        content = "\n".join(content_parts)

    else:
        # 降级：使用示例数据
        print()
        print("[WARN] 无法获取远程数据，降级使用内置示例数据")
        content = build_fallback_content()

    # 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] 知识库数据已写入: {OUTPUT_FILE}")
    print(f"[OK] 文件大小: {OUTPUT_FILE.stat().st_size} bytes")
    print(f"[OK] 行数: {content.count(chr(10)) + 1}")
    print()
    print("数据获取完成！")


if __name__ == "__main__":
    main()
