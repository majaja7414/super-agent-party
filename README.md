# super-agent-party

## 简介

## docker部署
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
docker pull python:3.12-slim 
docker build -t super-agent-party . 
docker run -d -p 3456:3456 super-agent-party:latest
```

## 源码部署
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
super\Scripts\activate # windows
# source super/bin/activate # linux or mac
pip install -r requirements.txt
npm install
python server.py
```