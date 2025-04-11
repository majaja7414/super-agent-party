@echo off
REM 检查是否已安装 cnpm，如果没有则安装 cnpm
WHERE cnpm >nul 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo cnpm not found, installing cnpm...
    CALL npm install -g cnpm --registry=https://registry.npmmirror.com
) ELSE (
    echo cnpm is already installed.
)

REM 创建超级虚拟环境
python -m venv super

REM 激活虚拟环境并安装Python依赖
CALL super\Scripts\activate.bat
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

REM 初始化Node.js环境
CALL cnpm install

REM 退出虚拟环境
CALL deactivate

echo.
echo Installation completed successfully!
pause