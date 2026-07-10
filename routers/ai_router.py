from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from services.claude_service import invoke_llm
from models.user_model import User
from dependencies import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])

class LLMRequest(BaseModel):
    prompt: str
    model: str = "claude_sonnet_4_6"

class LLMResponse(BaseModel):
    text: str

@router.post("/invoke", response_model=LLMResponse)
def invoke(request: LLMRequest, current_user: User = Depends(get_current_user)):
    try:
        result = invoke_llm(prompt=request.prompt, model=request.model)
        return LLMResponse(text=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))