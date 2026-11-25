from fastapi import HTTPException

import jwt

from cs.app.schemas import CurrentUser
from cs.common.settings import get_settings


def require_authorized_user(authorization:str|None,*roles:str)->CurrentUser:
    # 校验(认证)令牌authorization

    # 是否携带令牌
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 获取令牌
    access_token =  authorization.split(" ",1)[1] #authorization[len("bearer "):]

    # 解析(认证)令牌
    current_user = decode_token(access_token)
    if current_user.role not in roles:
        raise HTTPException(status_code=403, detail="forbidden")

    # 返回解析出来的用户对象
    return current_user

# 解析令牌
def decode_token(access_token:str)->CurrentUser:
    # 解析jwt字符串
    user_info_dict = jwt.decode(access_token,key = get_settings().jwt_secret,algorithms=["HS256"])

    # 返回解析结果
    return CurrentUser.model_validate(user_info_dict)

# 加密令牌
def encode_token(user:CurrentUser)->str:
    # 加密jwt字符串
    access_token = jwt.encode(user.model_dump(),key = get_settings().jwt_secret,algorithm="HS256")

    # 返回解析结果
    return access_token
