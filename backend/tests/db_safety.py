"""Fail closed when a test URL points at the application Neon endpoint."""
from sqlalchemy.engine import make_url


def assert_isolated(test_url, application_url):
    assert test_url and application_url, 'Both test and application URLs are required for isolation checks'
    test, application = make_url(test_url), make_url(application_url)
    def endpoint(url):
        return (url.host or '').lower().replace('-pooler', '')
    assert test.get_backend_name() == 'postgresql', 'PostgreSQL test URL required'
    assert endpoint(test) and endpoint(test) != endpoint(application), 'Refusing tests against application endpoint (including pooled/direct aliases)'
