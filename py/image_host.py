import logging
import os
import re

import requests
from py.get_setting import UPLOAD_FILES_DIR, load_settings


async def upload_image_host(url):
    settings = await load_settings()
    # 判断是否开启了图床功能
    if settings["BotConfig"]["imgHost_enabled"] and 'uploaded_files' in url:
        file_name = url.split("/")[-1]
        file_path = os.path.join(UPLOAD_FILES_DIR, file_name)
        
        # SM.MS图床处理
        if settings["BotConfig"]["imgHost"] == "smms":
            api_key = settings["BotConfig"].get("SMMS_api_key")
            if not api_key:
                logging.warning("SM.MS API key未配置，跳过上传")
                return url
            
            headers = {"Authorization": api_key}
            upload_url = "https://sm.ms/api/v2/upload"
            
            try:
                with open(file_path, "rb") as f:
                    files = {"smfile": (file_name, f)}
                    response = requests.post(upload_url, headers=headers, files=files)
                
                result = response.json()
                
                # 成功上传
                if response.status_code == 200 and result.get("success"):
                    return result["data"]["url"]
                
                # 处理重复图片情况
                elif result.get("code") == "image_repeated":
                    logging.info("检测到重复图片（已存在SM.MS服务器）")
                    
                    # 尝试从错误消息中提取URL
                    message = result.get("message", "")
                    url_match = re.search(r'https?://[^\s]+', message)
                    
                    if url_match:
                        existing_url = url_match.group(0)
                        logging.info(f"使用已有图片URL: {existing_url}")
                        return existing_url
                    
                    # 如果正则提取失败，尝试从images字段获取
                    elif result.get("images"):
                        existing_url = result["images"]
                        logging.info(f"使用已有图片URL: {existing_url}")
                        return existing_url
                    
                    # 如果都没有找到URL，返回原始URL
                    else:
                        logging.warning("无法从重复图片响应中提取URL")
                        return url
                
                # 处理其他错误
                else:
                    error_msg = result.get("message", "未知错误")
                    error_code = result.get("code", "未知代码")
                    logging.error(f"SM.MS上传失败: {error_msg} (代码: {error_code})")
            
            except Exception as e:
                logging.error(f"SM.MS上传异常: {str(e)}")
            return url
        
        # EasyImage图床处理（保留原有逻辑）
        elif settings["BotConfig"]["imgHost"] == "easyImage2":
            EI2_url = settings["BotConfig"]["EI2_base_url"]
            EI2_token = settings["BotConfig"]["EI2_api_key"]
            try:
                with open(file_path, "rb") as f:
                    files = {"image": (file_name, f)}
                    data = {"token": EI2_token}
                    response = requests.post(EI2_url, data=data, files=files)
                
                if response.status_code == 200:
                    return response.json().get("url")
                else:
                    logging.error(f"EasyImage上传失败: {response.status_code}")
            except Exception as e:
                logging.error(f"EasyImage上传异常: {str(e)}")
    
    return url