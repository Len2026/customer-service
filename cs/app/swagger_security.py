"""为 /docs 增加 Authorize（Bearer）按钮

原理：Swagger UI 的 Authorize 按钮 = 自动往请求加 `Authorization: Bearer <token>` 头。
而项目现有的鉴权依赖本来就通过 Header() 读取这个头
"""
from fastapi import FastAPI


class SwaggerAuth:
    """
    用法（在 app.py 里 `app = FastAPI()` 之后加）：
        from cs.app.swagger_security import SwaggerAuth
        SwaggerAuth(app)
    """

    def __init__(self, app: FastAPI, scheme_name: str = "BearerAuth"):
        self._scheme_name = scheme_name
        # 保存 FastAPI 原生的 openapi 生成函数
        self._original_openapi = app.openapi
        # 替换成「注入安全方案后」的版本
        app.openapi = self._openapi

    def _openapi(self):
        # 先走原生逻辑，拿到原始 schema
        schema = self._original_openapi()
        components = schema.setdefault("components", {})
        # 声明一个 HTTP Bearer 安全方案（这是 Authorize 按钮出现的依据）
        components["securitySchemes"] = {
            self._scheme_name: {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        # 全局 security：让 Authorize 按钮对所有接口生效
        schema["security"] = [{self._scheme_name: []}]
        return schema
