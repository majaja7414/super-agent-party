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