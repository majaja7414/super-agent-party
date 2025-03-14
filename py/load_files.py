import json
import os
from urllib.parse import urlparse
import aiohttp
from io import BytesIO
import asyncio

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

try:
    from odf import text
    from odf.opendocument import load
    from odf.teletype import extractText
except ImportError:
    text, load, extractText = None, None, None

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

office_extensions = {ext for group in FILE_FILTERS if group['name'] == '办公文档' for ext in group['extensions']}

async def handle_url(url):
    """异步处理URL输入"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            content = await response.read()
            path = urlparse(url).path
            ext = os.path.splitext(path)[1].lstrip('.').lower()
            return content, ext

async def handle_local_file(file_path):
    """异步处理本地文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    loop = asyncio.get_event_loop()
    content = await loop.run_in_executor(None, _read_file, file_path)
    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    return content, ext

def _read_file(file_path):
    """同步读取文件内容"""
    with open(file_path, 'rb') as f:
        return f.read()

async def get_content(input_str):
    """获取文件内容和扩展名"""
    if input_str.startswith(('http://', 'https://')):
        return await handle_url(input_str)
    else:
        return await handle_local_file(input_str)

def decode_text(content_bytes):
    """通用文本解码"""
    encodings = ['utf-8', 'gbk', 'iso-8859-1', 'latin-1']
    for enc in encodings:
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return content_bytes.decode('utf-8', errors='replace')

async def handle_office_document(content, ext):
    """异步处理办公文档"""
    handler = {
        'pdf': handle_pdf,
        'docx': handle_docx,
        'xlsx': handle_excel,
        'xls': handle_excel,
        'rtf': handle_rtf,
        'odt': handle_odt,
    }.get(ext)
    
    if handler:
        return await handler(content)
    raise NotImplementedError(f"暂不支持处理 {ext.upper()} 格式文件")

async def handle_odt(content):
    """异步处理ODT文件"""
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_odt, content)

def _process_odt(content):
    """同步处理ODT内容"""
    from odf.opendocument import load
    from odf.teletype import extractText
    
    try:
        doc = load(BytesIO(content))
        text_content = []
        # 提取所有段落文本
        for para in doc.getElementsByType(text.P):
            text_content.append(extractText(para))
        # 提取表格内容
        for table in doc.getElementsByType(text.Table):
            for row in table.getElementsByType(text.TableRow):
                row_data = []
                for cell in row.getElementsByType(text.TableCell):
                    row_data.append(extractText(cell))
                text_content.append("\t".join(row_data))
        return '\n'.join(text_content)
    except Exception as e:
        raise RuntimeError(f"ODT文件解析失败: {str(e)}")


async def handle_pdf(content):
    """异步处理PDF文件"""
    if not PdfReader:
        raise ImportError("请先安装 PyPDF2 库：pip install PyPDF2")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_pdf, content)

def _process_pdf(content):
    """同步处理PDF内容"""
    text = []
    with BytesIO(content) as pdf_file:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            text.append(page.extract_text())
    return '\n'.join(text)

async def handle_docx(content):
    """异步处理DOCX文件"""
    if not Document:
        raise ImportError("请先安装 python-docx 库：pip install python-docx")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_docx, content)

def _process_docx(content):
    """同步处理DOCX内容"""
    doc = Document(BytesIO(content))
    return '\n'.join(p.text for p in doc.paragraphs)

async def handle_excel(content):
    """异步处理Excel文件"""
    if not load_workbook:
        raise ImportError("请先安装 openpyxl 库：pip install openpyxl")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_excel, content)

def _process_excel(content):
    """同步处理Excel内容"""
    wb = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
    text = []
    for sheet in wb:
        for row in sheet.iter_rows(values_only=True):
            text.append('\t'.join(map(str, row)))
    return '\n'.join(text)

async def handle_rtf(content):
    """异步处理RTF文件"""
    if not rtf_to_text:
        raise ImportError("请先安装 striprtf 库：pip install striprtf")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_rtf, content)

def _process_rtf(content):
    """同步处理RTF内容"""
    return rtf_to_text(content.decode('utf-8', errors='replace'))

async def get_file_content(input_str):
    """异步获取文件内容"""
    content, ext = await get_content(input_str)
    if ext in office_extensions:
        return await handle_office_document(content, ext)
    return decode_text(content)

async def get_files_content(files_path_list):
    """异步获取所有文件内容并拼接"""
    tasks = [get_file_content(fp) for fp in files_path_list]
    contents = await asyncio.gather(*tasks)
    return "\n\n".join([f"文件 {fp} 内容：\n{content}" for fp, content in zip(files_path_list, contents)])
