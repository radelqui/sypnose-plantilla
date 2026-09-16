from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class CustomerIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)
        customer_id = request.headers.get("x-customer-id")
        if not customer_id:
            return JSONResponse(status_code=403, content={"detail": "X-Customer-Id requerido"})
        request.state.customer_id = customer_id
        return await call_next(request)
