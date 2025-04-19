import json
import os
import sys

def in_docker():
    try:
        with open('/proc/1/cgroup', 'rt') as ifh:
            for line in ifh:
                if 'docker' in line or 'container' in line:
                    return True
    except FileNotFoundError:
        # 如果文件不存在，则很可能不在容器中
        pass
    return False

if in_docker():
    HOST = '0.0.0.0'
else:
    HOST = '127.0.0.1'
PORT = 3456

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
        # 创建settings.json文件，并写入默认设置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
        if in_docker():
            settings['isdocker'] = True
        return default_settings
    
def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)