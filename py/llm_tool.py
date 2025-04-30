import base64
import json

import aiohttp
from py.get_setting import load_settings
from openai import AsyncOpenAI
from ollama import AsyncClient as OllamaClient


async def get_llm_tool(settings):
    llm_list = []

    llmTools = settings['llmTools']

    for llmTool in llmTools:
        if llmTool['enabled']:
            llm_list.append({"name": llmTool['name'], "description": llmTool['description']})
    if len(llm_list) > 0:
        llm_list = json.dumps(llm_list, ensure_ascii=False, indent=4)
        llm_tool = {
            "type": "function",
            "function": {
                "name": "llm_tool_call",
                "description": f"调用自定义的LLM工具，以下是工具列表：\n{llm_list}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "需要调用的工具名称",
                        },
                        "query": {
                            "type": "string",
                            "description": "需要向工具发送的问题",
                        },
                        "image_url": {
                            "type": "string",
                            "description": "需要向工具发送的图片URL，可选，来自本地服务器上的图片URL也可以填入（例如：http://127.0.0.1:3456/xxx.jpg），会被自动处理为base64编码发送",
                        }
                    },
                    "required": ["name","query"]
                }
            }
        }
        return llm_tool
    else:
        return None
    
async def get_image_base64(image_url: str) -> str:
    """下载图片并转换为base64编码"""
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise ValueError(f"Failed to download image from {image_url}")
            image_data = await response.read()
            return base64.b64encode(image_data).decode('utf-8')

async def llm_tool_call(name, query, image_url=None):
    print(f"调用LLM工具：{name}")
    settings = load_settings()
    llmTools = settings['llmTools']
    for llmTool in llmTools:
        if llmTool['enabled'] and llmTool['name'] == name:
            if llmTool['type'] == 'ollama':
                client = OllamaClient(host=llmTool['base_url'])
                try:
                    content = query
                    
                    # 处理图片输入
                    if image_url:
                        base64_image = await get_image_base64(image_url)
                        media_type = 'image/jpeg'  # 根据实际图片类型调整
                        content = [
                            {"type": "text", "text": query},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            }
                        ]

                    # 调用Ollama API
                    response = await client.chat(
                        model=llmTool['model'],
                        messages=[{"role": "user", "content": content}],
                    )
                    return response.message.content
                except Exception as e:
                    return str(e)
            else:
                client = AsyncOpenAI(api_key=llmTool['api_key'],base_url=llmTool['base_url'])
                try:
                    if image_url:
                        base64_image = await get_image_base64(image_url)
                        prompt = [
                            {
                                "type": "image",
                                "image_url": base64_image
                            },
                            {
                                "type": "text",
                                "text": query
                            }
                        ]
                        response = await client.chat.completions.create(
                            model=llmTool['model'],
                            messages=[
                                {"role": "user", "content": prompt},
                            ],
                        )
                    else:
                        response = await client.chat.completions.create(
                            model=llmTool['model'],
                            messages=[
                                {"role": "user", "content": query},
                            ],
                        )
                    return response.choices[0].message.content
                except Exception as e:
                    return str(e)