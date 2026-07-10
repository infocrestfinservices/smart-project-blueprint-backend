import os
from openai import OpenAI
from config import settings

client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

def invoke_llm(prompt: str, model: str = "deepseek-chat") -> str:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=8192,
        temperature=0.7
    )
    return response.choices[0].message.content