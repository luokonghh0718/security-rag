<#
.SYNOPSIS
    安全知识库 RAG 系统 - Windows 部署脚本
.DESCRIPTION
    将代码同步到远程服务器并启动 Docker 服务
.PARAMETER Server
    目标服务器地址，默认 192.168.10.133
.PARAMETER User
    SSH 用户名，默认 root
.PARAMETER Path
    远程部署路径，默认 /root/security-rag
.PARAMETER Port
    SSH 端口，默认 22
.EXAMPLE
    .\deploy.ps1
    .\deploy.ps1 -Server 10.0.0.100 -User admin -Path /home/admin/security-rag
#>

param(
    [string]$Server = "192.168.10.133",
    [string]$User = "root",
    [string]$RemotePath = "/root/security-rag",
    [int]$Port = 22
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安全知识库 RAG 系统 - 远程部署" -ForegroundColor Cyan
Write-Host "  目标: ${User}@${Server}:${RemotePath}" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检查 SSH 连接 ──────────────────────────────────
Write-Host "[1/4] 检查 SSH 连接..." -ForegroundColor Yellow
$sshTest = ssh -p $Port -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${User}@${Server}" "echo OK" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 无法连接到 ${Server}，请检查网络和 SSH 配置" -ForegroundColor Red
    Write-Host $sshTest
    exit 1
}
Write-Host "  [OK] SSH 连接正常" -ForegroundColor Green

# ── 2. 同步代码 ───────────────────────────────────────
Write-Host "[2/4] 同步代码到远程服务器..." -ForegroundColor Yellow

# 检查 rsync 是否可用
$rsyncAvailable = Get-Command rsync -ErrorAction SilentlyContinue

if ($rsyncAvailable) {
    Write-Host "  使用 rsync 同步..."
    $excludeArgs = @(
        "--exclude=node_modules",
        "--exclude=__pycache__",
        "--exclude=chroma_db",
        "--exclude=.git",
        "--exclude=dist",
        "--exclude=.env"
    )
    & rsync -avz -e "ssh -p $Port" @excludeArgs "$ScriptDir/" "${User}@${Server}:${RemotePath}/"
} else {
    Write-Host "  rsync 不可用，使用 scp 同步..."
    # 使用 scp 递归复制（排除项通过临时文件处理）
    $tempExclude = New-TemporaryFile
    @"
node_modules
__pycache__
chroma_db
.git
dist
.env
"@ | Out-File -FilePath $tempExclude -Encoding ASCII

    # 创建远程目录
    ssh -p $Port "${User}@${Server}" "mkdir -p ${RemotePath}"

    # 使用 scp 复制
    Get-ChildItem -Path $ScriptDir -Exclude @("node_modules", "__pycache__", "chroma_db", ".git", "dist", ".env") | ForEach-Object {
        $src = $_.FullName
        if ($_.PSIsContainer) {
            Write-Host "  上传目录: $($_.Name)"
            scp -r -P $Port "$src" "${User}@${Server}:${RemotePath}/"
        } else {
            scp -P $Port "$src" "${User}@${Server}:${RemotePath}/"
        }
    }
    Remove-Item $tempExclude
}
Write-Host "  [OK] 代码同步完成" -ForegroundColor Green

# ── 3. 远程部署 ────────────────────────────────────────
Write-Host "[3/4] 远程 Docker Compose 部署..." -ForegroundColor Yellow
$deployCmd = @"
cd ${RemotePath} && \
if [ ! -f .env ]; then cp .env.example .env && echo '  [INFO] 已创建 .env 文件，请填写 API Key'; fi && \
docker compose down && \
docker compose up -d --build && \
echo '  [OK] 部署完成'
"@

$deployResult = ssh -p $Port "${User}@${Server}" $deployCmd 2>&1
Write-Host $deployResult

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] 远程部署可能存在问题，请检查输出" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Docker 容器已启动" -ForegroundColor Green
}

# ── 4. 输出访问地址 ───────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  访问地址：" -ForegroundColor White
Write-Host "    前端:  http://${Server}:3000" -ForegroundColor Cyan
Write-Host "    后端:  http://${Server}:8000" -ForegroundColor Cyan
Write-Host "    API文档: http://${Server}:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  常用命令：" -ForegroundColor White
Write-Host "    ssh ${User}@${Server}" -ForegroundColor Gray
Write-Host "    ssh ${User}@${Server} 'cd ${RemotePath} && docker compose logs -f'" -ForegroundColor Gray
Write-Host "    ssh ${User}@${Server} 'cd ${RemotePath} && docker compose restart'" -ForegroundColor Gray
Write-Host ""
