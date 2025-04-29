import json
import os
import sys

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
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        # 与default_settings比较，如果缺少字段或者二级字段，则添加默认值
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
        # 如果运行在docker内部
        if in_docker():
            settings['isdocker'] = True
        return settings

    except FileNotFoundError:
        # 首次运行，创建配置文件
        settings = default_settings.copy()  # 重要！创建副本避免修改原默认配置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    # 公共的后处理逻辑
    if in_docker():
        settings['isdocker'] = True
    
    return settings
    
def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)