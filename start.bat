@echo off

:: 激活虚拟环境
call super\Scripts\activate.bat

start cmd /k "npm start"