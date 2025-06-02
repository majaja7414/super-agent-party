import asyncio
import json
import os
import time
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import requests
from tavily import TavilyClient
from py.get_setting import load_settings

async def DDGsearch_async(query):
    settings = await load_settings()
    def sync_search():
        max_results = settings['webSearch']['duckduckgo_max_results'] or 10
        try:
            with DDGS() as ddg:
                results = ddg.text(query, max_results=max_results)
            json.dumps(results, indent=2, ensure_ascii=False)
            return results
        except Exception as e:
            print(f"An error occurred: {e}")
            return ""

    try:
        # 使用默认executor在单独线程中执行同步操作
        return await asyncio.get_event_loop().run_in_executor(None, sync_search)
    except Exception as e:
        print(f"Event loop error: {e}")
        return ""
    
duckduckgo_tool = {
    "type": "function",
    "function": {
        "name": "DDGsearch_async",
        "description": f"通过关键词获得DuckDuckGo搜索上的信息。回答时，在回答的最下方给出信息来源。以链接的形式给出信息来源，格式为：[网站名称](链接地址)。返回链接时，不要让()内出现空格",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要搜索的关键词，可以是多个词语，多个词语之间用空格隔开。",
                },
            },
            "required": ["query"],
        },
    },
}

async def searxng_async(query):
    settings = await load_settings()
    def sync_search(query):
        max_results = settings['webSearch']['searxng_max_results'] or 10
        api_url = settings['webSearch']['searxng_url'] or "http://127.0.0.1:8080"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"q": query, "categories": "general","count": max_results}

        try:
            response = requests.get(api_url + "/search", headers=headers, params=params)
            html_content = response.text

            soup = BeautifulSoup(html_content, 'html.parser')
            results = []

            for result in soup.find_all('article', class_='result'):
                title = result.find('h3').get_text() if result.find('h3') else 'No title'
                link = result.find('a', class_='url_wrapper')['href'] if result.find('a', class_='url_wrapper') else 'No link'
                snippet = result.find('p', class_='content').get_text() if result.find('p', class_='content') else 'No snippet'
                
                results.append({
                    'title': title,
                    'link': link,
                    'snippet': snippet
                })

            return json.dumps(results, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"Search error: {e}")
            return ""

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_search, query)
    except Exception as e:
        print(f"Async error: {e}")
        return ""

searxng_tool = {
    "type": "function",
    "function": {
        "name": "searxng_async",
        "description": "通过SearXNG开源元搜索引擎获取网络信息。回答时，在回答的最下方给出信息来源。以链接的形式给出信息来源，格式为：[网站名称](链接地址)。返回链接时，不要让()内出现空格",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，支持自然语言和多关键词组合查询",
                },
            },
            "required": ["query"],
        },
    },
}


async def Tavily_search_async(query):
    settings = await load_settings()
    def sync_search():
        max_results = settings['webSearch']['tavily_max_results'] or 10
        try:
            api_key = settings['webSearch'].get('tavily_api_key', "")
            client = TavilyClient(api_key)
            response = client.search(
                query=query,
                max_results=max_results
            )
            return json.dumps(response, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Tavily search error: {e}")
            return ""

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_search)
    except Exception as e:
        print(f"Async execution error: {e}")
        return ""

tavily_tool = {
    "type": "function",
    "function": {
        "name": "Tavily_search_async",
        "description": "通过Tavily专业搜索API获取高质量的网络信息，特别适合获取实时数据和专业分析。回答时，在回答的最下方给出信息来源。以链接的形式给出信息来源，格式为：[网站名称](链接地址)。返回链接时，不要让()内出现空格",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要搜索的关键词或自然语言查询语句",
                }
            },
            "required": ["query"],
        },
    },
}

async def jina_crawler_async(original_url):
    settings = await load_settings()
    def sync_crawler():
        detail_url = "https://r.jina.ai/"
        url = f"{detail_url}{original_url}"
        try:
            jina_api_key = settings['webSearch'].get('jina_api_key', "")
            if jina_api_key:
                headers = {
                    'Authorization': f'Bearer {jina_api_key}',
                }
                response = requests.get(url, headers=headers)
            else:
                response = requests.get(url)
            if response.status_code == 200:
                return response.text
            else:
                return f"获取{original_url}网页信息失败，状态码：{response.status_code}"
        except requests.RequestException as e:
            return f"获取{original_url}网页信息失败，错误信息：{str(e)}"

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_crawler)
    except Exception as e:
        print(f"Async execution error: {e}")
        return ""

jina_crawler_tool = {
    "type": "function",
    "function": {
        "name": "jina_crawler_async",
        "description": "通过Jina AI的网页爬取API获取指定URL的网页内容。指定URL可以为其他搜索引擎搜索出来的网页链接，也可以是用户给出的网站链接。但不要将本机地址或内网地址开头的URL作为参数传入，因为jina将无法访问到这些URL。",
        "parameters": {
            "type": "object",
            "properties": {
                "original_url": {
                    "type": "string",
                    "description": "需要爬取的原始URL地址。",
                },
            },
            "required": ["original_url"],
        },
    },
}

class Crawl4AiTester:
    def __init__(self, base_url: str = "http://localhost:11235"):
        self.base_url = base_url

    def submit_and_wait(self, request_data: dict,headers: dict = None, timeout: int = 300) -> dict:
        # Submit crawl job
        response = requests.post(f"{self.base_url}/crawl", json=request_data,headers=headers)
        task_id = response.json()["task_id"]
        print(f"Task ID: {task_id}")

        # Poll for result
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Task {task_id} timeout")

            result = requests.get(f"{self.base_url}/task/{task_id}",headers=headers)
            status = result.json()

            if status["status"] == "completed":
                return status

            time.sleep(2)

async def Crawl4Ai_search_async(original_url):
    settings = await load_settings()
    def sync_search():
        try:
            tester = Crawl4AiTester()
            api_key = settings['webSearch'].get('Crawl4Ai_api_key', "test_api_code")
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
            request = {
                "urls": original_url,
                "priority": 10
            }
            result = tester.submit_and_wait(request, headers=headers)
            return result['result']['markdown']
        except Exception as e:
            return f"获取{original_url}网页信息失败，错误信息：{str(e)}"

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_search)
    except Exception as e:
        print(f"Async execution error: {e}")
        return ""

Crawl4Ai_tool = {
    "type": "function",
    "function": {
        "name": "Crawl4Ai_search_async",
        "description": "通过Crawl4Ai服务爬取指定URL的网页内容，返回Markdown格式的文本。回答时需在末尾以[网页标题](链接地址)格式标注来源（链接中避免空格）。",
        "parameters": {
            "type": "object",
            "properties": {
                "original_url": {
                    "type": "string",
                    "description": "需要爬取的目标URL地址。",
                }
            },
            "required": ["original_url"],
        },
    },
}

