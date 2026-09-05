"""统一错误类型与响应格式。

所有接口响应均包含 code 字段，且与 HTTP 状态码一致；
错误响应统一为 {"code": N, "msg": "...", "data": null}。
异常处理顺序遵循：401 > 403 > 400 > 429 > 409 > 404 > 500。
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class OJException(Exception):
    def __init__(self, status_code: int, msg: str):
        self.status_code = status_code
        self.msg = msg
        super().__init__(msg)


def error_response(status_code: int, msg: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "msg": msg, "data": None},
    )


def ok(msg: str, data):
    return {"code": 200, "msg": msg, "data": data}


def register_exception_handlers(app):
    @app.exception_handler(OJException)
    async def oj_exception_handler(request: Request, exc: OJException):
        return error_response(exc.status_code, exc.msg)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # FAQ 要求：FastAPI 默认 422 需要转为 400
        return error_response(400, "invalid parameters")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "error"
        return error_response(exc.status_code, detail)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 兜底：不向客户端泄露服务器内部细节
        return error_response(500, "internal server error")
