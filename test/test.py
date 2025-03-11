from openai import OpenAI

client = OpenAI(api_key="super",base_url="http://127.0.0.1:3456/v1")

try:
    response = client.chat.completions.create(
        model="qwen2.5:14b",
        messages=[
            {"role": "user", "content": "9.8和9.11哪个大？"},
        ],
        temperature=0.7,
        max_tokens=256,
    )
    response = response.model_dump_json()
    print(response)

except Exception as e:
    print(e)