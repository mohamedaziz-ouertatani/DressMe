"""
Passwords (bcrypt) and log-in tokens (JWT).

Every protected endpoint depends on `current_user`, which reads the token from
the "Authorization: Bearer <token>" header. For <img> tags (which cannot send
headers), image endpoints also accept ?token=<token>.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Query, Request
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
    return user


def current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer)):
    return _user_from_token(creds.credentials if creds else None, request)


def current_user_for_image(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer),
                           token: str | None = Query(None)):
    return _user_from_token(creds.credentials if creds else token, request)
