@echo off

:: 激活虚拟环境
call .venv\Scripts\activate.bat

start cmd /k "npm run dev"