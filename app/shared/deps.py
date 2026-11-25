from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.identity.auth import get_current_user, require_role
from app.identity.models import UserRole
from app.identity.schemas import UserContext

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[UserContext, Depends(get_current_user)]
OfficeUser = Annotated[UserContext, Depends(require_role(UserRole.provider_office))]
ReviewerUser = Annotated[UserContext, Depends(require_role(UserRole.reviewer))]
AdminUser = Annotated[UserContext, Depends(require_role(UserRole.ops_admin))]
MemberUser = Annotated[UserContext, Depends(require_role(UserRole.member))]
OfficeOrAdmin = Annotated[
    UserContext, Depends(require_role(UserRole.provider_office, UserRole.ops_admin))
]
