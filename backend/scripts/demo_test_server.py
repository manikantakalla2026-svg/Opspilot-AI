"""Local browser verification server. Uses ONLY the isolated test endpoint."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from dotenv import dotenv_values
from pydantic import SecretStr
from app.core.config import settings
from db_safety import assert_isolated
import uvicorn

if __name__ == '__main__':
    values = dotenv_values(Path(__file__).resolve().parents[1] / '.env.test.local')
    url = values.get('DATABASE_URL')
    assert_isolated(url, settings.database_url.get_secret_value() if settings.database_url else None)
    settings.database_url = SecretStr(url)
    settings.workspace_token = SecretStr('opspilot-browser-test')
    settings.ai_external_enabled = False
    settings.gemini_api_key = None
    settings.frontend_origins = ['http://127.0.0.1:5174']
    print('Isolated browser test server: synthetic data only; external AI disabled.')
    uvicorn.run('app.main:app', host='127.0.0.1', port=8010)
