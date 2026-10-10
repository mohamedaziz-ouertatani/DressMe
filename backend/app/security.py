"""
Passwords (bcrypt) and log-in tokens (JWT).

Every protected endpoint depends on `current_user`, which reads the token from
the "Authorization: Bearer <token>" header, and only there: a token in a URL
would leak into server logs, browser history and Referer headers. The app
loads protected images with fetch() + this header (see frontend ItemPhoto).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import object_id

bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def make_token(user_id, settings):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=settings.jwt_hours)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _user_from_token(token, request):
    if not token:
        raise HTTPException(401, "Not logged in")
    try:
        payload = jwt.decode(token, request.app.state.settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = request.app.state.db.users.find_one({"_id": object_id(payload.get("sub"))})
    if not user:
        raise HTTPException(401, "Unknown user")
    if user.get("disabled"):
        raise HTTPException(403, "This account is disabled")
    return user


def current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer)):
    return _user_from_token(creds.credentials if creds else None, request)


def current_admin(user=Depends(current_user)):
    """Admin-only endpoints (role set with python -m app.make_admin <email>)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    return user



def user_gender(user):
    """men / women, or None for an account created before the question existed."""
    return (user.get("profile") or {}).get("gender") or None


def gendered_user(user=Depends(current_user)):
    """Endpoints whose answer depends on the gender (outfit rules, shops, look-alikes, chat).
    An older account without one gets 409 until the app has asked it (PUT /me)."""
    if user_gender(user) is None:
        raise HTTPException(409, "gender_required")
    return user
