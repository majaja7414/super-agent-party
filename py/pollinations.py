from py.get_setting import load_settings

async def pollinations_image(prompt: str, width=512, height=512, model="flux"):
    settings = await load_settings()
    
    # Check if the provided values are default ones, if so, override them with settings
    if width == 512:
        width = settings["text2imgSettings"]["pollinations_width"]
    if height == 512:
        height = settings["text2imgSettings"]["pollinations_height"]
    if model == "flux":
        model = settings["text2imgSettings"]["pollinations_model"]
    
    # Convert prompt into a URL-compatible format
    prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&model={model}&nologo=true&enhance=true&private=true&safe=true"
    
    return f"[image]({url})"

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
                    "default":512
                },
                "height": {
                    "type": "number",
                    "description": "图片高度",
                    "default": 512
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