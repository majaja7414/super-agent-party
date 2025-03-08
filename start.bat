@echo off
start cmd /k "uvicorn server:app --reload"
start cmd /k "npm start"
