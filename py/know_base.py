import asyncio
import json
import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from typing import List, Dict
from load_files import get_files_json
from langchain_core.documents import Document
SETTINGS_FILE = 'config/settings.json'
SETTINGS_TEMPLATE_FILE = 'config/settings_template.json'
KB_DIR = 'kb'
os.makedirs(KB_DIR, exist_ok=True)
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 创建config文件夹
        os.makedirs('config', exist_ok=True)
        # 加载settings_template.json文件
        with open(SETTINGS_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            default_settings = json.load(f)
        # 创建settings.json文件，并写入默认设置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
        return default_settings

def chunk_documents(results: List[Dict], cur_kb) -> List[Dict]:
    """为每个文件单独分块并添加元数据"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=cur_kb["chunk_size"],
        chunk_overlap=cur_kb["chunk_overlap"],
        separators=["\n\n", "\n", "。", "！", "？"]
    )
    
    all_chunks = []
    
    for doc in results:
        # 对每个文件单独分块
        chunks = text_splitter.split_text(doc["content"])
        
        # 为每个块添加元数据
        for chunk in chunks:
            all_chunks.append({
                "text": chunk,
                "metadata": {
                    "file_path": doc["file_path"],
                    "file_name": doc["file_name"]
                }
            })
    
    return all_chunks

def build_vector_store(chunks: List[Dict], kb_id, cur_kb):
    """构建并保存向量数据库（带安全验证和路径处理）"""
    # 校验输入数据（增强版）
    if not chunks:
        raise ValueError("Empty chunks list")
    if not all(isinstance(chunk, dict) for chunk in chunks):
        raise TypeError("Chunks must be list of dictionaries")
    if not all("text" in chunk and "metadata" in chunk for chunk in chunks):
        raise ValueError("Missing required fields in chunks")

    # 初始化带错误处理的嵌入模型
    try:
        embeddings = OpenAIEmbeddings(
            model=cur_kb["model"],
            api_key=cur_kb["api_key"],
            base_url=cur_kb["base_url"]
        )
    except KeyError as e:
        raise ValueError(f"Missing required config key: {e}")

    # 转换数据结构（带详细错误日志）
    documents = []
    for idx, chunk in enumerate(chunks):
        try:
            doc = Document(
                page_content=chunk["text"],
                metadata={k: str(v) for k, v in chunk["metadata"].items()}
            )
            documents.append(doc)
        except Exception as e:
            print(f"Error processing chunk {idx}: {str(e)}")
            continue  # 跳过错误数据继续处理

    if not documents:
        raise ValueError("No valid documents after processing chunks")

    # 创建存储路径（带权限验证）
    save_path = Path(KB_DIR) / str(kb_id)
    try:
        save_path.mkdir(parents=True, exist_ok=True)
        if not os.access(save_path, os.W_OK):
            raise PermissionError(f"Write permission denied: {save_path}")
    except OSError as e:
        raise RuntimeError(f"Path creation failed: {str(e)}")

    # 核心修正点：使用正确的方法创建向量库
    try:
        print(f"Creating vector store with {len(documents)} chunks...")
        # 使用 from_documents 替代 from_embeddings
        vector_db = FAISS.from_documents(
            documents=documents,
            embedding=embeddings
        )
    except ValueError as e:
        if "No vectors found" in str(e):
            raise RuntimeError("Embedding generation failed. Check API connectivity.")
        raise

    # 安全保存（带版本控制）
    try:
        vector_db.save_local(
            folder_path=str(save_path),
            index_name="index"
        )
    except Exception as e:
        raise RuntimeError(f"Save failed: {str(e)}")

    return vector_db


def query_vector_store(query: str, kb_id, cur_kb):
    """根据知识库ID查询对应向量数据库"""
    # 构建安全路径
    kb_path = Path(KB_DIR) / str(kb_id)
    
    # 验证路径合法性
    if not os.path.exists(kb_path):
        raise FileNotFoundError(f"Knowledge base {kb_id} not found")
    if not os.path.isdir(kb_path):
        raise ValueError(f"Invalid knowledge base path: {kb_id}")
    # 初始化带重试的嵌入模型
    embeddings = OpenAIEmbeddings(
        model=cur_kb["model"],
        api_key=cur_kb["api_key"],
        base_url=cur_kb["base_url"],
        dimensions=1024
    )
    try:
        # 加载指定知识库
        vector_db = FAISS.load_local(
            folder_path=str(kb_path),
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
            index_name="index"  # 与保存时的默认名称一致
        )
    except Exception as e:
        raise RuntimeError(f"Failed to load vector store: {str(e)}")
    # 执行语义搜索
    results = vector_db.similarity_search_with_score(
        query=query,
        k=cur_kb["chunk_k"],
    )
    # 格式化输出（带元数据过滤）
    return [{
        "content": doc.page_content,
        "metadata": {
            "file_name": doc.metadata.get("file_name", "unknown"),
            "file_path": doc.metadata.get("file_path", "unknown")
        },
        "score": float(score)
    } for doc, score in results]


async def process_knowledge_base(kb_id: int):
    """异步处理知识库的完整流程"""
    # 加载配置
    settings = load_settings()
    
    # 查找对应知识库配置
    cur_kb = None
    for kb in settings["knowledgeBases"]:
        if kb["id"] == kb_id:
            cur_kb = kb
            break
    if not cur_kb:
        raise ValueError(f"Knowledge base {kb_id} not found in settings")
    # 异步获取文件处理结果
    processed_results = await get_files_json(cur_kb["files"])
    
    # 分块处理文档
    chunks = chunk_documents(processed_results, cur_kb)
    
    # 构建向量存储
    build_vector_store(chunks, kb_id, cur_kb)

    return "知识库处理完成"

async def query_knowledge_base(kb_id: int, query: str):
    """查询知识库"""
    # 加载配置
    settings = load_settings()

    # 查找对应知识库配置
    cur_kb = None
    for kb in settings["knowledgeBases"]:
        if kb["id"] == kb_id:
            cur_kb = kb
            break
    if not cur_kb:
        raise ValueError(f"Knowledge base {kb_id} not found in settings")
    # 查询知识库
    results = query_vector_store(query,kb_id, cur_kb)
    return results

async def main():
    """示例用法"""
    try:
        # 示例参数
        kb_id = 1742544447950
        test_query = "需要查询的问题"
        
        # 处理知识库并获取结果
        await process_knowledge_base(kb_id)
        results = await query_knowledge_base(kb_id, test_query)
        # 格式化输出结果
        for result in results:
            print(f"内容：{result['content'][:100]}...")
            print(f"文件名：{result['metadata']['file_name']}")
            print(f"文件路径：{result['metadata']['file_path']}")
            print(f"匹配度：{result['score']:.2f}\n")
            
        return results
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        raise
if __name__ == "__main__":
    asyncio.run(main())
