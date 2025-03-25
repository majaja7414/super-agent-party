import asyncio
import json
import os
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import requests
from tavily import TavilyClient

SETTINGS_FILE = 'config/settings.json'
SETTINGS_TEMPLATE_FILE = 'config/settings_template.json'
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 创建config文件夹
        os.makedirs('config', exist_ok=True)
        # 加载settings_template.json文件
        with open(SETTINGS_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            default_settings = json.load(f)
        # 创建settings.json文件，并写入默认设置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
        return default_settings

async def DDGsearch_async(query):
    def sync_search():
        settings = load_settings()
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
    def sync_search(query):
        settings = load_settings()
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
    def sync_search():
        settings = load_settings()
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
    def sync_crawler():
        detail_url = "https://r.jina.ai/"
        url = f"{detail_url}{original_url}"
        settings = load_settings()
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
                    "description": "需要爬取的原始URL地址",
                },
            },
            "required": ["original_url"],
        },
    },
}

