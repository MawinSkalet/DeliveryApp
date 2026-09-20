from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.errors import ApiError, api_error_handler, validation_error_handler
from app.orders import router as orders_router
from app.products import router as products_router
from app.users import auth_router, users_router

app = FastAPI(title="DeliveryApp API", version="0.1.0")
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(products_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
