"""Durable access-token revocation records.

Audit finding H-01: revocation lived only in Redis, with an in-process
``deque`` fallback. That fallback is per-worker, so a revocation written by
worker A was invisible to worker B, and when Redis was unavailable
``is_revoked`` returned ``jti in _fallback`` -- a revoked token kept
authenticating on every worker whose local deque did not happen to contain it.
That is a fail-open revocation path.

The fix is not "fail closed on Redis errors" alone: that would log out the
entire user base during any Redis blip. Revocation needs an authoritative
store that is as available as the database the request already depends on.

So: revocation is written to this table (authoritative, transactional, shared
by every worker) *and* to Redis (a fast cache). Reads use Redis; when Redis is
unavailable they fall through to this table. Correctness no longer depends on
Redis being up, and availability no longer depends on it either.

Rows are pruned by ``app.core.tasks`` once ``expires_at`` has passed: after
the token's own expiry the revocation is redundant, because the token is
rejected by its ``exp`` claim.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.base import Base


class RevokedToken(Base):
    """One row per revoked access token, keyed by its JWT ``jti``."""

    __tablename__ = "revoked_tokens"
    __table_args__ = (
        # Supports the pruning sweep without scanning the table.
        Index("ix_revoked_tokens_expires_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The JWT ID. Unique: revoking twice is idempotent, not an error.
    jti = Column(String(64), nullable=False, unique=True, index=True)

    # Nullable so a token whose subject cannot be resolved is still revocable.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # The token's own expiry. After this instant the row carries no
    # information and is safe to delete.
    expires_at = Column(DateTime(timezone=True), nullable=False)

    reason = Column(Text)

    revoked_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<RevokedToken {self.jti} until {self.expires_at}>"
