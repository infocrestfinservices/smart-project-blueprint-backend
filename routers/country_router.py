from fastapi import APIRouter

router = APIRouter(
    prefix="/countries",
    tags=["Countries"]
)

@router.get("/")
def get_countries():
    return [
        {"id":1,"name":"India"},
        {"id":2,"name":"USA"},
        {"id":3,"name":"UK"}
    ]