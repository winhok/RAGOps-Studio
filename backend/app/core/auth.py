from __future__ import annotations
import hashlib
import hmac
import json
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.errors import ConfigurationError, Forbidden
from app.core.models import Principal
bearer = HTTPBearer(auto_error=False)

class CredentialRegistry:
    """Resolve opaque credentials into a server-owned tenant/department identity."""

    def __init__(self, path: Path):
        self.path = path

    def resolve(self, token: str) -> Principal:
        if not self.path.exists():
            raise ConfigurationError('Identity configuration is missing. Run scripts/bootstrap.py first.')
        try:
            rows = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(rows, list) or any(not isinstance(row, dict) or 'token_sha256' not in row or 'principal' not in row for row in rows):
                raise ValueError('Invalid registry')
        except (ValueError, OSError) as exc:
            raise ConfigurationError('Identity configuration is invalid; contact the administrator') from exc
        digest = hashlib.sha256(token.encode()).hexdigest()
        for row in rows:
            if hmac.compare_digest(row['token_sha256'], digest):
                return Principal.model_validate(row['principal'])
        raise HTTPException(401, 'Invalid or revoked credential', headers={'WWW-Authenticate': 'Bearer'})

def current_principal(request: Request, credentials: HTTPAuthorizationCredentials | None=Depends(bearer)) -> Principal:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
    return request.app.state.credentials.resolve(credentials.credentials)

def require_admin(principal: Principal=Depends(current_principal)) -> Principal:
    if principal.role != 'admin':
        raise Forbidden('Only a tenant administrator can maintain documents or run evaluations')
    return principal

def can_read(principal: Principal, tenant_id: str, department_id: str, visibility: str) -> bool:
    return principal.tenant_id == tenant_id and (principal.role == 'admin' or visibility == 'company' or principal.department_id == department_id)
