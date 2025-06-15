import os

import requests
from py.get_setting import UPLOAD_FILES_DIR, load_settings


async def upload_image_host(url):
    settings = await load_settings()
    # 判断是否开启了图床功能
    if settings["BotConfig"]["imgHost_enabled"] and 'uploaded_files' in url:
        if settings["BotConfig"]["imgHost"] == "easyImage2":
            EI2_url = settings["BotConfig"]["EI2_base_url"]
            EI2_token = settings["BotConfig"]["EI2_api_key"]
            # 上传图片到图床
            file_name = url.split("/")[-1]
            file_path = os.path.join(UPLOAD_FILES_DIR, file_name)
            data = {
                "token": EI2_token
            }
            with open(file_path, "rb") as f:
                files = {
                    "image": (file_path, f)
                }
                response = requests.post(EI2_url, data=data, files=files)
            if response.status_code == 200:
                # 打印返回的 JSON 数据中的url字段
                url = response.json().get("url")
            else:
                print("上传失败")
    return url