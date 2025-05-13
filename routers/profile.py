from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from model.models import User, Guardian
from pydantic import BaseModel

router = APIRouter()

class ProfileResponse(BaseModel):
    name: str
    role: str
    birth: str
    contact: str

    class Config:
        orm_mode = True

@router.get("/profile/", response_model=ProfileResponse)
async def get_profile(id: str, role: str, db: AsyncSession = Depends(get_db)):
    """
    현재 로그인된 사용자 또는 보호자의 정보를 반환합니다.
    - id: user_id 또는 guardian_id
    - role: 'user' 또는 'guardian'
    """
    if role == "user":
        result = await db.execute(select(User).where(User.user_id == id))
        user = result.scalar()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return ProfileResponse(
            name=user.name,
            role="사용자",
            birth=user.birth,
            contact=user.contact
        )

    elif role == "guardian":
        result = await db.execute(select(Guardian).where(Guardian.guardian_id == id))
        guardian = result.scalar()
        if not guardian:
            raise HTTPException(status_code=404, detail="Guardian not found")
        return ProfileResponse(
            name=guardian.name,
            role="보호자",
            birth=guardian.birth,
            contact=guardian.contact
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid role (must be 'user' or 'guardian')")
