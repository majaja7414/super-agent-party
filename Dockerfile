# 使用官方Python镜像
FROM python:3.12-slim

# 安装Node.js（使用Debian包管理器）
RUN apt-get update && \
    apt-get install -y gcc curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \ 
    apt-get install -y nodejs

# 设置工作目录
WORKDIR /app

# 先单独复制依赖清单文件
COPY requirements.txt ./

COPY package.json package-lock.json ./

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装Node依赖（自动读取package-lock.json）
RUN npm install --production --legacy-peer-deps  # 兼容性模式

# 复制其他项目文件（通过.dockerignore排除node_modules）
COPY . .

# 创建上传目录
RUN mkdir -p uploaded_files

# 暴露端口和环境变量
EXPOSE 3456
ENV HOST=0.0.0.0 PORT=3456 PYTHONUNBUFFERED=1

# 启动命令
CMD ["sh", "-c", "python server.py --host $HOST --port $PORT"]
