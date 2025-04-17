#!/bin/bash

# 创建超级虚拟环境
python3 -m venv super

# 激活虚拟环境并安装Python依赖
source super/bin/activate
pip install -r requirements.txt

# 初始化Node.js环境
npm install

# 退出虚拟环境
deactivate

echo ""
echo "Installation completed successfully!"