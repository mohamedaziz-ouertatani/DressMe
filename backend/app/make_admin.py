"""
Give an existing account the admin role (there is no way to become admin from the app).

Run from the backend/ folder, after the person has signed up:
    python -m app.make_admin someone@example.com
    python -m app.make_admin someone@example.com --remove     # back to a normal user
"""

import argparse
import sys

from .config import Settings
from .db import connect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--remove", action="store_true", help="remove the admin role")
    args = ap.parse_args()
    db = connect(Settings())
    role = "user" if args.remove else "admin"
    result = db.users.update_one({"email": args.email.lower()}, {"$set": {"role": role}})
    if not result.matched_count:
        sys.exit(f"No account with the email {args.email}")
    print(f"{args.email} is now {role}")


if __name__ == "__main__":
    main()
