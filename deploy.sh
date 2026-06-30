#!/bin/bash
# ===============================================
# 安全知识库 RAG 系统 - Linux/Mac 部署脚本
# ===============================================
set -e

# ── 配置 ──────────────────────────────────────────
SERVER="${1:-192.168.10.133}"
USER="${2:-root}"
REMOTE_PATH="${3:-/root/security-rag}"
SSH_PORT="${4:-22}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  安全知识库 RAG 系统 - 远程部署"
echo "  目标: ${USER}@${SERVER}:${REMOTE_PATH}"
echo "========================================"
echo ""

# ── 1. 检查 SSH 连接 ──────────────────────────────
echo -e "\033[33m[1/4] 检查 SSH 连接...\033[0m"
if ! ssh -p "$SSH_PORT" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${USER}@${SERVER}" "echo OK" &>/dev/null; then
    echo -e "\033[31m[ERROR] 无法连接到 ${SERVER}，请检查网络和 SSH 配置\033[0m"
    exit 1
fi
echo -e "\033[32m  [OK] SSH 连接正常\033[0m"

# ── 2. 同步代码 ────────────────────────────────────
echo -e "\033[33m[2/4] 同步代码到远程服务器...\033[0m"

EXCLUDES=(
    --exclude='node_modules'
    --exclude='__pycache__'
    --exclude='chroma_db'
    --exclude='.git'
    --exclude='dist'
    --exclude='.env'
    --exclude='*.pyc'
)

if command -v rsync &>/dev/null; then
    echo "  使用 rsync 同步..."
    rsync -avz -e "ssh -p $SSH_PORT" "${EXCLUDES[@]}" "$SCRIPT_DIR/" "${USER}@${SERVER}:${REMOTE_PATH}/"
else
    echo "  rsync 不可用，使用 scp 同步..."
    ssh -p "$SSH_PORT" "${USER}@${SERVER}" "mkdir -p ${REMOTE_PATH}"
    # 查找并上传文件（排除指定目录）
    find "$SCRIPT_DIR" -type f \
        ! -path "*/node_modules/*" \
        ! -path "*/__pycache__/*" \
        ! -path "*/.git/*" \
        ! -path "*/dist/*" \
        ! -name ".env" \
        ! -name "*.pyc" \
        -printf '%P\n' | while read -r file; do
        dir=$(dirname "$file")
        if [ "$dir" != "." ]; then
            ssh -p "$SSH_PORT" "${USER}@${SERVER}" "mkdir -p ${REMOTE_PATH}/${dir}"
        fi
        scp -P "$SSH_PORT" "$SCRIPT_DIR/$file" "${USER}@${SERVER}:${REMOTE_PATH}/${file}"
    done
fi
echo -e "\033[32m  [OK] 代码同步完成\033[0m"

# ── 3. 远程部署 ────────────────────────────────────
echo -e "\033[33m[3/4] 远程 Docker Compose 部署...\033[0m"
ssh -p "$SSH_PORT" "${USER}@${SERVER}" << REMOTE_SCRIPT
set -e
cd ${REMOTE_PATH}

# 如果没有 .env 则从模板创建
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  [INFO] 已创建 .env 文件，请填写 API Key"
fi

# 停止旧容器并重新构建启动
docker compose down
docker compose up -d --build

echo "  [OK] Docker 容器已启动"
REMOTE_SCRIPT

echo -e "\033[32m  [OK] 部署完成\033[0m"

# ── 4. 输出访问地址 ────────────────────────────────
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "  访问地址："
echo -e "    前端:  \033[36mhttp://${SERVER}:3000\033[0m"
echo -e "    后端:  \033[36mhttp://${SERVER}:8000\033[0m"
echo -e "    API文档: \033[36mhttp://${SERVER}:8000/docs\033[0m"
echo ""
echo "  常用命令："
echo "    ssh ${USER}@${SERVER}"
echo "    ssh ${USER}@${SERVER} 'cd ${REMOTE_PATH} && docker compose logs -f'"
echo "    ssh ${USER}@${SERVER} 'cd ${REMOTE_PATH} && docker compose restart'"
echo ""
