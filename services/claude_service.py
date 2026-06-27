import anthropic
from config import settings

MODEL_MAP = {
    "claude_sonnet_4_6": "claude-sonnet-4-5",
    "claude_sonnet":     "claude-sonnet-4-5",
    "claude_opus":       "claude-opus-4-5",
}

client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

def invoke_llm(prompt: str, model: str = "claude_sonnet_4_6") -> str:
    anthropic_model = MODEL_MAP.get(model, model)
    message = client.messages.create(
        model=anthropic_model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text