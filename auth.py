from datetime import datetime, timedelta
import jwt

import falcon

from config import AppConfig
def create_access_token(data: dict, config: AppConfig, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.config['session_secret_key'], algorithm="HS256")

def get_current_user(req: falcon.Request, config: AppConfig) -> dict:
    auth_header = req.get_header("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise falcon.HTTPUnauthorized(title="Missing or invalid token")

    token = auth_header.split(" ")[1]
    try:
        user = extract_user(token, config.config['session_secret_key'])
        return user
    except Exception as e:
        raise e
    
def extract_user(token: str, session_secret: str) -> dict:
    try:
        payload = jwt.decode(token, session_secret, algorithms="HS256")
        user = payload.get("user")
        if not user:
            raise falcon.HTTPForbidden(title="Invalid token")
        return user
    except jwt.PyJWTError:
        raise falcon.HTTPForbidden(title="Invalid token")