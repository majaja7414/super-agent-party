async def pollinations_image(prompt: str,width=1024,height=1024,model="flux"):
    # 把prompt转换成可以插入URL的格式
    prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&model={model}&nologo=true&enhance=true&private=true&safe=true"
    return f"![image]({url})"

pollinations_image_tool = {
    "type": "function",
    "function": {
        "name": "pollinations_image",
        "description": "通过英文prompt生成图片，并返回markdown格式的图片链接，你可以直接以原markdown格式发给用户即可，用户将会直接看到图片",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "需要生成图片的英文prompt，例如：A little girl in a red hat。你可以尽可能的丰富你的prompt，以获得更好的效果",
                },
                "width": {
                    "type": "number",
                    "description": "图片宽度",
                    "default":1024
                },
                "height": {
                    "type": "number",
                    "description": "图片高度",
                    "default": 1024
                },
                "model": {
                    "type": "string",
                    "description": "使用的模型",
                    "default": "flux",
                    "enum": ["flux", "turbo"],
                }
            },
            "required": ["prompt"],
        },
    },
}