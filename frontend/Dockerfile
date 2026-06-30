# ── 第一阶段：构建 React 应用 ──
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package.json ./

# 安装依赖
RUN npm install --legacy-peer-deps

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# ── 第二阶段：Nginx 托管 ──
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
