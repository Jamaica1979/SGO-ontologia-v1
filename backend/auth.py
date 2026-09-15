import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
ADMIN_USER = os.environ.get("ADMIN_USER", "eldorado")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "cantera2026")


def verificar_acceso(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    pass_ok = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"})
    return credentials.username
