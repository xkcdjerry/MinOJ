"""语言注册与查询 API（Step 2）。"""
from fastapi import APIRouter, Depends

from app import storage
from app.deps import get_current_user
from app.errors import ok
from app.schemas import LanguageModel

router = APIRouter()


@router.post("/api/languages/")
async def register_language(body: LanguageModel, current_user: dict = Depends(get_current_user)):
    await storage.db.languages.put(body.name, body.model_dump())
    return ok("language registered", {"name": body.name})


@router.get("/api/languages/")
async def list_languages():
    names = sorted(storage.db.languages.data.keys())
    return ok("success", {"name": names})
