import aiohttp

async def fetch_custom_http(method, url, headers=None, body=None):
    # 如果 headers 为空字符串或 None，则设置为默认的空字典
    if headers is None or headers == "":
        headers = {}

    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, json=body) as response:
            # 获取响应状态
            print(f'Status: {response.status}')
            # 获取响应文本
            response_text = await response.text()
            print(f'Response: {response_text}')
            return response_text