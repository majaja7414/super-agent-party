import asyncio
import json
import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from typing import List, Dict
if __name__ == "__main__":
    from load_files import get_files_json
else:
    from py.load_files import get_files_json
from langchain_core.documents import Document
from py.get_setting import load_settings

KB_DIR = 'kb'
os.makedirs(KB_DIR, exist_ok=True)


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

def build_vector_store(chunks: List[Dict], kb_id, cur_kb, cur_vendor):
    """构建并保存向量数据库（支持分批处理）"""
    # 校验输入数据
    if not chunks:
        raise ValueError("Empty chunks list")
    if not all(isinstance(chunk, dict) for chunk in chunks):
        raise TypeError("Chunks must be list of dictionaries")
    if not all("text" in chunk and "metadata" in chunk for chunk in chunks):
        raise ValueError("Missing required fields in chunks")

    # 初始化嵌入模型
    try:
        if cur_vendor == "Ollama":
            embeddings = OllamaEmbeddings(
                model=cur_kb["model"],
                base_url=cur_kb["base_url"].rstrip("/v1").rstrip("/v1/")
            )
        else:
            embeddings = OpenAIEmbeddings(
                model=cur_kb["model"],
                openai_api_key=cur_kb["api_key"],
                openai_api_base=cur_kb["base_url"],
            )
    except KeyError as e:
        raise ValueError(f"Missing required config key: {e}")

    # 转换文档数据结构
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
    
    if not documents:
        raise ValueError("No valid documents after processing chunks")

    # 创建存储路径
    save_path = Path(KB_DIR) / str(kb_id)
    try:
        save_path.mkdir(parents=True, exist_ok=True)
        if not os.access(save_path, os.W_OK):
            raise PermissionError(f"Write permission denied: {save_path}")
    except OSError as e:
        raise RuntimeError(f"Path creation failed: {str(e)}")

    # 分批处理文档（每5个一批）
    batch_size = 5
    vector_db = None
    total_batches = (len(documents) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = start_idx + batch_size
        current_batch = documents[start_idx:end_idx]

        try:
            if vector_db is None:
                # 第一批次创建新数据库
                vector_db = FAISS.from_documents(
                    documents=current_batch,
                    embedding=embeddings
                )
            else:
                # 后续批次增量添加
                vector_db.add_documents(current_batch)
            
            print(f"Processed batch {batch_num + 1}/{total_batches} "
                  f"({len(current_batch)} documents)")

        except Exception as e:
            print(f"Failed to process batch {batch_num + 1}: {str(e)}")
            # 可以选择记录失败批次以便后续重试
            continue

    if vector_db is None:
        raise RuntimeError("Failed to create vector store from all batches")

    # 最终保存整个数据库
    try:
        vector_db.save_local(
            folder_path=str(save_path),
            index_name="index"
        )
    except Exception as e:
        raise RuntimeError(f"Save failed: {str(e)}")

    return vector_db



def query_vector_store(query: str, kb_id, cur_kb,cur_vendor):
    """根据知识库ID查询对应向量数据库"""
    # 构建安全路径
    kb_path = Path(KB_DIR) / str(kb_id)
    
    # 验证路径合法性
    if not os.path.exists(kb_path):
        raise FileNotFoundError(f"Knowledge base {kb_id} not found")
    if not os.path.isdir(kb_path):
        raise ValueError(f"Invalid knowledge base path: {kb_id}")
    # 初始化带重试的嵌入模型
    if cur_vendor == "Ollama":
        embeddings = OllamaEmbeddings(
            model=cur_kb["model"],
            base_url=cur_kb["base_url"].rstrip("/v1").rstrip("/v1/")
        )
    else:
        embeddings = OpenAIEmbeddings(
            model=cur_kb["model"],
            openai_api_key=cur_kb["api_key"],
            openai_api_base=cur_kb["base_url"],
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
            providerId = kb["providerId"]
            break
    cur_vendor = None
    for provider in settings["modelProviders"]:
        if provider["id"] == providerId:
            cur_vendor = provider["vendor"]
            break
    
    if not cur_kb:
        raise ValueError(f"Knowledge base {kb_id} not found in settings")
    # 异步获取文件处理结果
    processed_results = await get_files_json(cur_kb["files"])
    
    # 分块处理文档
    chunks = chunk_documents(processed_results, cur_kb)
    
    # 构建向量存储
    build_vector_store(chunks, kb_id, cur_kb,cur_vendor)

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
            providerId = kb["providerId"]
            break
    cur_vendor = None
    for provider in settings["modelProviders"]:
        if provider["id"] == providerId:
            cur_vendor = provider["vendor"]
            break
    
    if not cur_kb:
        return f"Knowledge base {kb_id} not found in settings"
    # 查询知识库
    results = query_vector_store(query,kb_id, cur_kb,cur_vendor)
    return json.dumps(results, ensure_ascii=False, indent=2)

kb_tool = {
    "type": "function",
    "function": {
        "name": "query_knowledge_base",
        "description": f"通过自然语言获取的对应ID的知识库信息。回答时，在回答的最下方给出信息来源。以链接的形式给出信息来源，格式为：[file_name](file_path)。file_path可以是外部资源，也可以是127.0.0.1上的资源。返回链接时，不要让()内出现空格",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要搜索的问题。",
                },
                "kb_id": {
                    "type": "integer",
                    "description": "知识库的ID。"
                }
            },
            "required": ["kb_id","query"],
        },
    },
}


async def main():
    """示例用法"""
    try:
        # 示例参数
        kb_id = 1742632861261
        test_query = "什么是LLM party？"
        
        # 处理知识库并获取结果
        await process_knowledge_base(kb_id)
        results = await query_knowledge_base(kb_id, test_query)

        # 打印结果
        print(results)

        return results
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        raise
if __name__ == "__main__":
    asyncio.run(main())