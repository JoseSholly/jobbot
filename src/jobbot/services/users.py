"""User administration that the Python side needs (bootstrap + admin CLI).

Day-to-day onboarding (/start, invites, approvals) runs in the Cloudflare Worker,
which implements the same rules against the same tables.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from jobbot.domain.models import User, UserStatus
from jobbot.interfaces.repositories import InviteRepository, UserRepository

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


class UserService:
    def __init__(
        self,
        users: UserRepository,
        invites: InviteRepository,
        default_ng_quota: int = 4,
        default_global_quota: int = 6,
    ):
        self.users = users
        self.invites = invites
        self.default_ng_quota = default_ng_quota
        self.default_global_quota = default_global_quota

    def ensure_admin(self, chat_id: int, username: str | None = None) -> User:
        user = self.users.get(chat_id) or User(
            chat_id=chat_id,
            username=username,
            status=UserStatus.ACTIVE,
            ng_quota=self.default_ng_quota,
            global_quota=self.default_global_quota,
        )
        user.status = UserStatus.ACTIVE
        user.is_admin = True
        self.users.upsert(user)
        return user

    def set_status(self, chat_id: int, status: UserStatus) -> User:
        user = self.users.get(chat_id)
        if user is None:
            raise LookupError(f"unknown user {chat_id}")
        user.status = status
        self.users.upsert(user)
        return user

    def create_invite(self, created_by: int, max_uses: int = 1, days_valid: int | None = 14) -> str:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        expires = datetime.now(UTC) + timedelta(days=days_valid) if days_valid else None
        self.invites.create(code, created_by, max_uses, expires)
        return code

    def list_users(self) -> list[User]:
        return sorted(self.users.list_all(), key=lambda u: (u.status, u.chat_id))
