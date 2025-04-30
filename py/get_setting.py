import json
import os
import sys
import aiofiles

HOST = None
PORT = None
def configure_host_port(host, port):
    global HOST, PORT
    HOST = host
    PORT = port
def get_host():
    return HOST or "127.0.0.1"  # 提供默认值
def get_port():
    return PORT or 3456

def in_docker():
    def check_cgroup():
        try:
            with open('/proc/1/cgroup', 'rt',encoding='utf-8') as ifh:
                for line in ifh:
                    if 'docker' in line or 'container' in line:
                        return True
        except FileNotFoundError:
            pass
        return False

    def check_dockerenv():
        try:
            with open('/.dockerenv', 'rt',encoding='utf-8') as ifh:
                # 文件存在即表示是在Docker容器中
                return True
        except FileNotFoundError:
            return False

    def check_proc_self_status():
        try:
            with open('/proc/self/status', 'rt',encoding='utf-8') as ifh:
                for line in ifh:
                    if line.startswith('Context') and 'container=docker' in line:
                        return True
        except FileNotFoundError:
            pass
        return False
    
    return any([check_cgroup(), check_dockerenv(), check_proc_self_status()])

def get_base_path():
    """判断当前是开发环境还是打包环境，返回基础路径"""
    if getattr(sys, 'frozen', False):
        # 打包后，资源在 sys._MEIPASS 指向的临时目录
        return sys._MEIPASS
    else:
        # 开发环境使用当前工作目录
        return os.path.abspath(".")
base_path = get_base_path()
CONFIG_BASE_PATH = os.path.join(base_path, 'config')
os.makedirs(CONFIG_BASE_PATH, exist_ok=True)
SETTINGS_FILE = os.path.join(CONFIG_BASE_PATH, 'settings.json')
SETTINGS_TEMPLATE_FILE = os.path.join(CONFIG_BASE_PATH, 'settings_template.json')
with open(SETTINGS_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
    default_settings = json.load(f)

async def load_settings():
    try:
        async with aiofiles.open(SETTINGS_FILE, mode='r', encoding='utf-8') as f:
            contents = await f.read()
            settings = json.loads(contents)

        # 补充缺失的字段（包括嵌套字段）
        def merge_defaults(default, target):
            for key, value in default.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict):
                    merge_defaults(value, target[key])

        merge_defaults(default_settings, settings)

        # 设置 isdocker 字段
        if in_docker():
            settings['isdocker'] = True

        return settings

    except FileNotFoundError:
        # 首次运行，创建配置文件
        settings = default_settings.copy()

        if in_docker():
            settings['isdocker'] = True

        await save_settings(settings)
        return settings


async def save_settings(settings):
    async with aiofiles.open(SETTINGS_FILE, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(settings, ensure_ascii=False, indent=2))