from fastapi import APIRouter

router = APIRouter(
    prefix="/industries",
    tags=["Industries"]
)

@router.get("/")
def get_industries():
    return [
        {"id":1,"name":"Restaurant"},
        {"id":2,"name":"Manufacturing"},
        {"id":3,"name":"Healthcare"}
    ]