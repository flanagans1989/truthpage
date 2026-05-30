import logging
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.tenant import Tenant
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_SESSION_COOKIE = "session"

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
)


async def get_current_tenant(
    session_token: str | None = Cookie(default=None, alias=_SESSION_COOKIE),
    db: AsyncSession = Depends(get_db_session),
) -> Tenant:
    if not session_token:
        raise _credentials_exc

    try:
        payload = jwt.decode(session_token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
        tenant_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if not tenant_id_str or token_type != "session":
            raise _credentials_exc
        tenant_id = UUID(tenant_id_str)
    except (jwt.PyJWTError, ValueError):
        raise _credentials_exc

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise _credentials_exc

    return tenant


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
