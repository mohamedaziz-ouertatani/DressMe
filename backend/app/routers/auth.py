"""Sign-up, log-in and the user's profile (name, modesty level, language)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from ..schemas import Login, ProfileUpdate, Register
from ..security import check_password, current_user, hash_password, make_token

router = APIRouter(tags=["auth"])


def profile_out(user):
    return {"id": str(user["_id"]), "email": user["email"], "role": user.get("role", "user"),
            "demo": bool(user.get("demo")), **user["profile"]}


@router.post("/auth/register", status_code=201)
def register(body: Register, request: Request):
    db, settings = request.app.state.db, request.app.state.settings
    user = {"email": body.email.lower(), "password_hash": hash_password(body.password),
            "profile": {"name": body.name, "min_coverage": None, "language": "en"},
            "role": "user", "disabled": False,
            "created_at": datetime.now(timezone.utc)}
    try:
        user["_id"] = db.users.insert_one(user).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, "This email already has an account")
    return {"token": make_token(user["_id"], settings), "user": profile_out(user)}


@router.post("/auth/login")
def login(body: Login, request: Request):
    db, settings = request.app.state.db, request.app.state.settings
    user = db.users.find_one({"email": body.email.lower()})
    # same message for unknown email and wrong password (do not reveal which)
    if not user or not check_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    if user.get("disabled"):
        raise HTTPException(403, "This account is disabled")
    return {"token": make_token(user["_id"], settings), "user": profile_out(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    return profile_out(user)


@router.put("/me")
def update_me(body: ProfileUpdate, request: Request, user=Depends(current_user)):
    changes = {f"profile.{k}": v for k, v in body.model_dump(exclude_unset=True).items()}
    if changes:
        request.app.state.db.users.update_one({"_id": user["_id"]}, {"$set": changes})
    return profile_out(request.app.state.db.users.find_one({"_id": user["_id"]}))
