from openai import OpenAI

client = OpenAI(api_key="super",base_url="http://127.0.0.1:3456/v1")

try:
    response = client.chat.completions.create(
        model="qwen2.5:14b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Who won the world series in 2020?"},
        ],
        temperature=0.7,
        max_tokens=256,
    )

    print(response.choices[0].message.content)

except Exception as e:
    print(e)