from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.routes import router
from app.api.analysis import router as analysis_router
from app.core.config import settings
from app.core.body_limit import AnalysisBodyLimit
from app.db.session import build_engine

app = FastAPI(title='OpsPilot AI', version='0.2.0')
app.add_middleware(AnalysisBodyLimit)
app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins,
                   allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                   allow_headers=['Content-Type', 'X-Workspace-Token', 'X-Ingestion-Key'])
app.include_router(router)
app.include_router(analysis_router)


def database_engine():
    return build_engine(settings.database_url)


@app.exception_handler(IntegrityError)
async def conflict_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={'detail': 'Conflicting record; service names must be unique'})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=503, content={'detail': 'Database unavailable; please retry'})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': list(e['loc']), 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]})


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'OpsPilot AI API'}


@app.get('/health/db')
def database_health():
    if not settings.database_url:
        return JSONResponse(status_code=503, content={'status': 'not_configured'})
    engine = None
    try:
        engine = database_engine()
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status': 'ok'}
    except (SQLAlchemyError, ValueError):
        return JSONResponse(status_code=503, content={'status': 'unavailable'})
    finally:
        if engine is not None:
            engine.dispose()
