"""Sign-up, log-in and the user's profile (name, gender, modesty level, language)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from ..accounts import delete_account
from ..schemas import DeleteMe, Login, ProfileUpdate, Register
from ..security import check_password, current_user, hash_password, make_token

router = APIRouter(tags=["auth"])


def profile_out(user):
    profile = {"gender": None, "budget_tnd": None, **user["profile"]}
    return {"id": str(user["_id"]), "email": user["email"], "role": user.get("role", "user"),
            "demo": bool(user.get("demo")), **profile,
            "consent_at": user["consent_at"].isoformat() if user.get("consent_at") else None,   # null: asked once
            "needs_gender": profile["gender"] is None}   # accounts from before: asked once


@router.post("/auth/register", status_code=201)
def register(body: Register, request: Request):
    db, settings = request.app.state.db, request.app.state.settings
    user = {"email": body.email.lower(), "password_hash": hash_password(body.password),
            "profile": {"name": body.name, "gender": body.gender, "min_coverage": None,
                        "language": "en"},
            "role": "user", "disabled": False,
            "created_at": datetime.now(timezone.utc)}
    if body.consent:
        user["consent_at"] = user["created_at"]
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


@router.post("/me/consent")
def give_consent(request: Request, user=Depends(current_user)):
    """The one-time dialog of an account made before the consent checkbox. Idempotent: a second call keeps
    the first date."""
    users = request.app.state.db.users
    users.update_one({"_id": user["_id"], "consent_at": None}, {"$set": {"consent_at": datetime.now(timezone.utc)}})
    return profile_out(users.find_one({"_id": user["_id"]}))


# TODO(step 5): no "last admin" guard: an admin can delete their own account here even if it is the only admin
# (academic scope). The full version refuses it, and could keep a short grace period before the data goes.
@router.delete("/me", status_code=204)
def delete_me(body: DeleteMe, request: Request, user=Depends(current_user)):
    if user.get("demo"):
        raise HTTPException(403, "The demo account cannot be deleted")
    if not check_password(body.password, user["password_hash"]):
        raise HTTPException(403, "Wrong password")
    delete_account(request, user)
    return Response(status_code=204)
