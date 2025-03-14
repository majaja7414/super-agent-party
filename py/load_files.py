import json
import os
from urllib.parse import urlparse
import requests
from io import BytesIO

# 办公文档处理库检测
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    rtf_to_text = None

# 文件类型配置
FILE_FILTERS = [
    { 
        'name': '办公文档', 
        'extensions': ['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'pages', 'numbers', 'key', 'rtf', 'odt'] 
    },
    { 
        'name': '编程开发', 
        'extensions': [
            'js', 'ts', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs',
            'swift', 'kt', 'dart', 'rb', 'php', 'html', 'css', 'scss',
            'less', 'vue', 'svelte', 'jsx', 'tsx', 'json', 'xml', 'yml',
            'yaml', 'sql', 'sh'
        ]
    },
    {
        'name': '数据配置',
        'extensions': ['csv', 'tsv', 'txt', 'md', 'log', 'conf', 'ini', 'env', 'toml']
    }
]

# 生成办公文档扩展名集合
office_extensions = set()
for group in FILE_FILTERS:
    if group['name'] == '办公文档':
        office_extensions.update(group['extensions'])

def get_file_content(input_str):
    """获取文件内容，支持本地路径和URL，返回文本字符串"""
    content, ext = get_content(input_str)
    
    if ext in office_extensions:
        return handle_office_document(content, ext)
    return decode_text(content)

def get_content(input_str):
    """获取文件内容和扩展名"""
    if input_str.startswith(('http://', 'https://')):
        content, ext = handle_url(input_str)
    else:
        content, ext = handle_local_file(input_str)
    return content, ext

def handle_url(url):
    """处理URL输入"""
    response = requests.get(url)
    response.raise_for_status()
    content = response.content
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    return content, ext

def handle_local_file(file_path):
    """处理本地文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(file_path, 'rb') as f:
        content = f.read()
    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    return content, ext

def decode_text(content_bytes):
    """通用文本解码"""
    encodings = ['utf-8', 'gbk', 'iso-8859-1', 'latin-1']
    for enc in encodings:
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return content_bytes.decode('utf-8', errors='replace')

def handle_office_document(content, ext):
    """处理办公文档"""
    handlers = {
        'pdf': handle_pdf,
        'docx': handle_docx,
        'xlsx': handle_excel,
        'xls': handle_excel,
        'rtf': handle_rtf,
        'odt': handle_odt,
    }
    
    handler = handlers.get(ext)
    if handler:
        return handler(content)
    raise NotImplementedError(f"暂不支持处理 {ext.upper()} 格式文件")

def handle_pdf(content):
    """处理PDF文件"""
    if not PdfReader:
        raise ImportError("请先安装 PyPDF2 库：pip install PyPDF2")
    text = []
    with BytesIO(content) as pdf_file:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            text.append(page.extract_text())
    return '\n'.join(text)

def handle_docx(content):
    """处理DOCX文件"""
    if not Document:
        raise ImportError("请先安装 python-docx 库：pip install python-docx")
    doc = Document(BytesIO(content))
    return '\n'.join(p.text for p in doc.paragraphs)

def handle_excel(content):
    """处理Excel文件"""
    if not load_workbook:
        raise ImportError("请先安装 openpyxl 库：pip install openpyxl")
    wb = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
    text = []
    for sheet in wb:
        for row in sheet.iter_rows(values_only=True):
            text.append('\t'.join(map(str, row)))
    return '\n'.join(text)

def handle_rtf(content):
    """处理RTF文件"""
    if rtf_to_text:
        return rtf_to_text(content.decode('utf-8', errors='replace'))
    return content.decode('utf-8', errors='replace')

def handle_odt(content):
    """处理ODT文件"""
    try:
        from odf import text
        from odf.opendocument import load
        from odf.teletype import extractText
    except ImportError:
        raise ImportError("请先安装 odfpy 库：pip install odfpy")
    
    doc = load(BytesIO(content))
    text_content = []
    for para in doc.getElementsByType(text.P):
        text_content.append(extractText(para))
    return '\n'.join(text_content)


def get_files_content(files_path_list):
    """获取文件内容"""
    files_content= []
    for file_path in files_path_list:
        content = get_file_content(file_path)
        files_content.append({'content': content, 'file_path': file_path})
    files_content = json.dumps(files_content, ensure_ascii=False) # 将文件内容转换为JSON格式
    return files_content

# 示例用法
if __name__ == "__main__":
    # 使用本地文件
    print(get_file_content("D:/AI/PARTY-O/super-API-party/uploaded_files/丰富英国灵媒帕克部分5a8b5e1e-b238-43f2-93a3-488b0aa88ad0.docx"))
    
    # 使用URL
    # print(get_file_content("https://example.com/sample.pdf"))
