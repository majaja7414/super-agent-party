import datetime
import logging
import os
import re
import signal
import sys
import time
from typing import List
import botpy
from botpy.message import C2CMessage,GroupMessage
from openai import AsyncOpenAI
from pydantic import BaseModel
import requests

from py.get_setting import PORT, UPLOAD_FILES_DIR, load_settings

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

class MyClient(botpy.Client):
    def __init__(self,start_event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_running = False
        self.QQAgent = "super-model"
        self.memoryLimit = 10
        self.memoryList = {}
        self.start_event = start_event
        self.separators = ['。', '\n', '？', '！']
        self.reasoningVisible = False
        self.quickRestart = True

    async def on_ready(self):
        self.is_running = True
        self.start_event.set()

    async def on_c2c_message_create(self, message: C2CMessage):
        if not self.is_running:
            return
        client = AsyncOpenAI(
            api_key="super-secret-key",
            base_url=f"http://127.0.0.1:{PORT}/v1"
        )
        user_content = []
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image/"):
                    image_url = attachment.url
                    user_content.append({"type": "image_url", "image_url": {"url": image_url}})
        if user_content:
            user_content.append({"type": "text", "text": message.content})
        else:
            user_content = message.content
        print(f"User content: {user_content}")
        c_id = message.author.user_openid
        if c_id not in self.memoryList:
            self.memoryList[c_id] = []
        if self.quickRestart:
            if "/restart" in message.content or "/重启" in message.content:
                self.memoryList[c_id] = []
        self.memoryList[c_id].append({"role": "user", "content": user_content})

        # 初始化状态管理
        if not hasattr(self, 'msg_seq_counters'):
            self.msg_seq_counters = {}
        self.msg_seq_counters.setdefault(c_id, 1)
        
        if not hasattr(self, 'processing_states'):
            self.processing_states = {}
        self.processing_states[c_id] = {
            "text_buffer": "",
            "image_buffer": "",
            "image_cache": []
        }

        try:
            # 流式调用API
            stream = await client.chat.completions.create(
                model=self.QQAgent,
                messages=self.memoryList[c_id],
                stream=True
            )
            
            full_response = []
            async for chunk in stream:
                reasoning_content = ""
                if chunk.choices:
                    chunk_dict = chunk.model_dump()
                    delta = chunk_dict["choices"][0].get("delta", {})
                    if delta:
                        reasoning_content = delta.get("reasoning_content", "") 
                content = chunk.choices[0].delta.content or ""
                full_response.append(content)
                if reasoning_content and self.reasoningVisible:
                    content = reasoning_content
                
                # 更新缓冲区
                state = self.processing_states[c_id]
                state["text_buffer"] += content
                state["image_buffer"] += content

                # 处理文本实时发送
                while True:
                    if self.separators == []:
                        break
                    # 查找分隔符（。或\n）
                    buffer = state["text_buffer"]
                    split_pos = -1
                    for i, c in enumerate(buffer):
                        if c in self.separators:
                            split_pos = i + 1
                            break
                    if split_pos == -1:
                        break

                    # 分割并处理当前段落
                    current_chunk = buffer[:split_pos]
                    state["text_buffer"] = buffer[split_pos:]
                    
                    # 清洗并发送文字
                    clean_text = self._clean_text(current_chunk)
                    if clean_text:
                        await self._send_text_message(message, clean_text)
                    
            # 提取图片到缓存（不发送）
            self._extract_images_to_cache(c_id)

            # 处理剩余文本
            if state["text_buffer"]:
                clean_text = self._clean_text(state["text_buffer"])
                if clean_text:
                    await self._send_text_message(message, clean_text)
            
            # 最终图片发送
            await self._send_cached_images(message)

            # 记忆管理
            full_content = "".join(full_response)
            self.memoryList[c_id].append({"role": "assistant", "content": full_content})
            if self.memoryLimit > 0:
                while len(self.memoryList[c_id]) > self.memoryLimit:
                    self.memoryList[c_id].pop(0)

        except Exception as e:
            print(f"处理异常: {e}")
            clean_text = self._clean_text(str(e))
            if clean_text:
                await self._send_text_message(message, clean_text)
        finally:
            # 清理状态
            del self.processing_states[c_id]

    def _extract_images_to_cache(self, c_id):
        """渐进式图片链接提取"""
        state = self.processing_states[c_id]
        temp_buffer = state["image_buffer"]
        state["image_buffer"] = ""  # 重置缓冲区
        
        # 匹配完整图片链接
        pattern = r'!\[.*?\]\((https?://[^\s\)]+)'
        matches = re.finditer(pattern, temp_buffer)
        for match in matches:
            state["image_cache"].append(match.group(1))

    async def _send_text_message(self, message, text):
        """发送文本消息并更新序号"""
        c_id = message.author.user_openid
        await message._api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0,
            msg_id=message.id,
            content=text,
            msg_seq=self.msg_seq_counters[c_id]
        )
        self.msg_seq_counters[c_id] += 1

    async def _send_cached_images(self, message):
        """批量发送缓存的图片"""
        c_id = message.author.user_openid
        state = self.processing_states.get(c_id, {})
        
        for url in state.get("image_cache", []):
            try:
                # 链接有效性验证
                if not re.match(r'^https?://', url):
                    continue
                # 判断是否开启了图床功能
                url = await upload_image_host(url)
                # 用request获取图片，保证图片存在
                res = requests.get(url)

                print(f"发送图片: {url}")
                # 上传媒体文件
                upload_media = await message._api.post_c2c_file(
                    openid=message.author.user_openid,
                    file_type=1,
                    url=url
                )
                # 发送富媒体消息
                await message._api.post_c2c_message(
                    openid=message.author.user_openid,
                    msg_type=7,
                    msg_id=message.id,
                    media=upload_media,
                    msg_seq=self.msg_seq_counters[c_id]
                )
                self.msg_seq_counters[c_id] += 1
            except Exception as e:
                print(f"图片发送失败: {e}")
                clean_text = self._clean_text(str(e))
                if clean_text:
                    await self._send_text_message(message, clean_text)

    def _clean_text(self, text):
        """三级内容清洗"""
        # 移除图片标记
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # 移除超链接
        clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)
        # 移除纯URL
        clean = re.sub(r'https?://\S+', '', clean)
        return clean.strip()

    
    async def on_group_at_message_create(self, message: GroupMessage):
        if not self.is_running:
            return
        
        client = AsyncOpenAI(
            api_key="super-secret-key",
            base_url=f"http://127.0.0.1:{PORT}/v1"
        )
        user_content = []
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith("image/"):
                    image_url = attachment.url
                    try:
                        # 用request获取图片，保证图片存在
                        response = requests.get(image_url)
                        user_content.append({"type": "image_url", "image_url": {"url": image_url}})
                    except Exception as e:
                        print(f"图片获取失败: {e}")
        if user_content:
            user_content.append({"type": "text", "text": message.content})
        else:
            user_content = message.content
        g_id = message.group_openid
        if g_id not in self.memoryList:
            self.memoryList[g_id] = []
        if self.quickRestart:
            if "/restart" in message.content or "/重启" in message.content:
                self.memoryList[g_id] = []
        self.memoryList[g_id].append({"role": "user", "content": user_content})

        # 初始化群组状态
        if not hasattr(self, 'group_states'):
            self.group_states = {}
        self.group_states[g_id] = {
            "msg_seq": 1,
            "text_buffer": "",
            "image_buffer": "",
            "image_cache": []
        }

        try:
            # 流式API调用
            stream = await client.chat.completions.create(
                model=self.QQAgent,
                messages=self.memoryList[g_id],
                stream=True
            )
            
            full_response = []
            async for chunk in stream:
                reasoning_content = ""
                if chunk.choices:
                    chunk_dict = chunk.model_dump()
                    delta = chunk_dict["choices"][0].get("delta", {})
                    if delta:
                        reasoning_content = delta.get("reasoning_content", "")
                content = chunk.choices[0].delta.content or ""
                full_response.append(content)
                if reasoning_content and self.reasoningVisible:
                    content = reasoning_content
                state = self.group_states[g_id]
                
                # 更新文本缓冲区
                state["text_buffer"] += content
                state["image_buffer"] += content

                # 处理文本分段
                while True:
                    if self.separators == []:
                        break
                    # 查找分隔符（。或\n）
                    buffer = state["text_buffer"]
                    split_pos = -1
                    for i, c in enumerate(buffer):
                        if c in self.separators:
                            split_pos = i + 1
                            break
                    if split_pos == -1:
                        break

                    # 处理当前段落
                    current_chunk = buffer[:split_pos]
                    state["text_buffer"] = buffer[split_pos:]
                    
                    # 清洗并发送文字
                    clean_text = self._clean_group_text(current_chunk)
                    if clean_text:
                        await self._send_group_text(message, clean_text, state)
                    
            # 提取图片到缓存
            self._cache_group_images(g_id)

            # 处理剩余文本
            if self.group_states[g_id]["text_buffer"]:
                clean_text = self._clean_group_text(self.group_states[g_id]["text_buffer"])
                if clean_text:
                    await self._send_group_text(message, clean_text, state)

            # 发送缓存图片
            await self._send_group_images(message, g_id)

            # 记忆管理
            full_content = "".join(full_response)
            self.memoryList[g_id].append({"role": "assistant", "content": full_content})
            if self.memoryLimit > 0:
                while len(self.memoryList[g_id]) > self.memoryLimit:
                    self.memoryList[g_id].pop(0)

        except Exception as e:
            print(f"群聊处理异常: {e}")
            clean_text = self._clean_group_text(str(e))
            if clean_text:
                await self._send_group_text(message, clean_text, state)
        finally:
            # 清理状态
            del self.group_states[g_id]

    def _cache_group_images(self, g_id):
        """渐进式图片缓存"""
        state = self.group_states[g_id]
        temp_buffer = state["image_buffer"]
        state["image_buffer"] = ""
        
        # 匹配完整图片链接
        pattern = r'!\[.*?\]\((https?://[^\s\)]+)'
        matches = re.finditer(pattern, temp_buffer)
        for match in matches:
            state["image_cache"].append(match.group(1))

    async def _send_group_text(self, message, text, state):
        """发送群聊文字消息"""
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=text,
            msg_seq=state["msg_seq"]
        )
        state["msg_seq"] += 1

    async def _send_group_images(self, message, g_id):
        """批量发送群聊图片"""
        state = self.group_states.get(g_id, {})
        for url in state.get("image_cache", []):
            try:
                # 链接有效性验证
                if not url.startswith(('http://', 'https://')):
                    continue
                # 判断是否开启了图床功能
                url = await upload_image_host(url)
                # 用request获取图片，保证图片存在
                res = requests.get(url)
                print(f"发送图片: {url}")
                # 上传群文件
                upload_media = await message._api.post_group_file(
                    group_openid=message.group_openid,
                    file_type=1,
                    url=url
                )
                # 发送群媒体消息
                await message._api.post_group_message(
                    group_openid=message.group_openid,
                    msg_type=7,
                    msg_id=message.id,
                    media=upload_media,
                    msg_seq=state["msg_seq"]
                )
                state["msg_seq"] += 1
            except Exception as e:
                print(f"群图片发送失败: {e}")
                clean_text = self._clean_group_text(str(e))
                if clean_text:
                    self._send_group_text(message, clean_text, state)

    def _clean_group_text(self, text):
        """群聊文本三级清洗"""
        # 移除图片标记
        clean = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # 移除超链接
        clean = re.sub(r'\[.*?\]\(.*?\)', '', clean)
        # 移除纯URL
        clean = re.sub(r'https?://\S+', '', clean)
        return clean.strip()

# 定义请求体
class QQBotConfig(BaseModel):
    QQAgent: str
    memoryLimit: int
    appid: str
    secret: str
    separators: List[str]
    reasoningVisible: bool
    quickRestart: bool
    
def run_bot_process_wrapper(config: QQBotConfig, start_event, shared_dict, env_vars):
    """包装函数，用于设置子进程环境"""
    try:
        # 更新环境变量
        os.environ.update(env_vars)
        
        # 调用实际的机器人进程函数
        run_bot_process(config, start_event, shared_dict)
    except Exception as e:
        shared_dict['error'] = f"子进程包装异常: {str(e)}"
        start_event.set()

def run_bot_process(config: QQBotConfig, start_event, shared_dict):
    """在新进程中运行机器人的函数"""
    try:
        # 确保 freeze_support
        from multiprocessing import freeze_support
        freeze_support()
        
        # 检查是否是 Electron 子进程
        is_electron_child = os.environ.get('ELECTRON_CHILD_PROCESS') == '1'
        
        shared_dict['debug'] = f"子进程启动，PID: {os.getpid()}, Electron子进程: {is_electron_child}"
        
        # Windows 和 Electron 特殊处理
        if sys.platform == 'win32':
            import subprocess
            subprocess._cleanup = lambda: None
            
            # 隐藏控制台窗口
            if is_electron_child or os.environ.get('CREATE_NO_WINDOW'):
                try:
                    import ctypes
                    whnd = ctypes.windll.kernel32.GetConsoleWindow()
                    if whnd != 0:
                        ctypes.windll.user32.ShowWindow(whnd, 0)  # 隐藏窗口
                except Exception as e:
                    shared_dict['warning'] = f"隐藏控制台失败: {str(e)}"
        
        # 配置日志
        log_path = 'bot_electron.log' if is_electron_child else 'bot.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

        logger = logging.getLogger("QQBotProcess")
        logger.info(f"机器人子进程启动 (Electron: {is_electron_child})")
        
        # 其余代码保持不变，但增加更多错误处理
        try:
            client = MyClient(start_event, intents=botpy.Intents(public_messages=True))
            client.QQAgent = config.QQAgent
            client.memoryLimit = config.memoryLimit
            client.separators = config.separators
            client.reasoningVisible = config.reasoningVisible
            client.quickRestart = config.quickRestart
            
            logger.info("开始运行QQ机器人...")
            shared_dict['status'] = 'starting'
            
            # 运行机器人
            client.run(appid=config.appid, secret=config.secret)
            
        except Exception as bot_error:
            error_msg = f"机器人运行异常: {str(bot_error)}"
            logger.error(error_msg)
            shared_dict['error'] = error_msg
            start_event.set()
        
    except Exception as e:
        error_msg = f"子进程初始化异常: {str(e)}"
        shared_dict['error'] = error_msg
        start_event.set()
        
        # 记录到日志文件
        try:
            with open('bot_error.log', 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now()}: {error_msg}\n")
        except:
            pass