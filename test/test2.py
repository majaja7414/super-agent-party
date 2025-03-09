from openai import OpenAI
import json
import os

def test_with_official_sdk():
    """使用官方SDK测试自定义端点"""
    print("\n=== 使用OpenAI SDK测试 ===")
    
    # 初始化自定义客户端
    client = OpenAI(
        base_url="http://127.0.0.1:3456/v1",
        api_key="sk-anykey"  # 根据你的settings.json配置
    )

    try:
        # 测试1: 获取模型列表
        print("\n[测试1] 获取模型列表")
        models = client.models.list()
        print(f"找到 {len(models.data)} 个模型")
        
        # 打印前3个模型信息
        for model in models.data[:3]:
            print(f" - {model.id} (创建时间: {model.created})")

        # 测试2: 基础聊天请求
        print("\n[测试2] 聊天请求测试")
        completion = client.chat.completions.create(
            model=models.data[1].id,  # 使用第一个可用模型
            messages=[{"role": "user", "content": "Hello!"}],
            max_tokens=20
        )
        print(f"响应示例: {completion.choices[0].message.content}")

        # 测试3: 错误处理
        print("\n[测试3] 错误请求测试")
        try:
            _ = client.chat.completions.create(
                model="invalid_model",
                messages=[{"role": "user", "content": "test"}]
            )
        except Exception as e:
            print(f"捕获到预期错误: {type(e).__name__}")
            print(f"错误信息: {str(e)}")

    except Exception as e:
        print(f"\n[!] 测试失败: {str(e)}")
    finally:
        print("\n=== 测试结束 ===")

if __name__ == "__main__":
    # 确保服务已启动
    print("请确保服务运行在 http://localhost:3456")
    
    # 执行测试
    test_with_official_sdk()
