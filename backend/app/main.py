from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.db import close_pool
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.mongo import close_mongo_client
from app.orders import router as orders_router
from app.products import ensure_catalog_indexes, router as products_router
from app.users import auth_router, users_router

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        ensure_catalog_indexes()
        yield
    finally:
        try:
            close_pool()
        finally:
            close_mongo_client()


app = FastAPI(title="DeliveryApp API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(products_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
