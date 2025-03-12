@echo off
REM 创建超级虚拟环境
python -m venv super

REM 激活虚拟环境并安装Python依赖
CALL super\Scripts\activate.bat
pip install -r requirements.txt

REM 初始化Node.js环境
CALL npm install

REM 退出虚拟环境
CALL deactivate

echo.
echo Installation completed successfully!
pause