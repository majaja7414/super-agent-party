@echo off

:: 激活虚拟环境
call super\Scripts\activate.bat

:: 在新的命令提示符中启动Uvicorn（端口3456）
start cmd /k "uvicorn server:app --reload --port 3456"

:: 在另一个新的命令提示符中启动npm start
start cmd /k "npm start"
