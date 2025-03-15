import asyncio
from duckduckgo_search import DDGS

async def DDGsearch_async(query, max_results=10):
    def sync_search():
        try:
            with DDGS() as ddg:
                return ddg.text(query, max_results=max_results)
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    try:
        # 使用默认executor在单独线程中执行同步操作
        return await asyncio.get_event_loop().run_in_executor(None, sync_search)
    except Exception as e:
        print(f"Event loop error: {e}")
        return []
    
duckduckgo_tool = {
    "type": "function",
    "function": {
        "name": "search_duckduckgo",
        "description": f"通过关键词获得DuckDuckGo搜索上的信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "需要搜索的关键词，可以是多个词语，多个词语之间用空格隔开。",
                },
            },
            "required": ["keywords"],
        },
    },
}