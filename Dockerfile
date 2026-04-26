# 使用 Python 3.10 作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8765

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动 Web 服务
# run_web.py 启动 FastAPI 服务器，监听 0.0.0.0:8765
# 提供 Web 图形界面和 WebSocket API
CMD ["python", "run_web.py"]
