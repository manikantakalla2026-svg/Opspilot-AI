"""Optional pure ASGI middleware; it does not alter the exception or response."""
from .client import OpsPilot


class OpsPilotMiddleware:
    def __init__(self, app, client: OpsPilot | None = None):
        self.app = app
        self.client = client

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            try:
                # Route templates avoid collecting user IDs embedded in raw URLs.
                route = scope.get("route")
                endpoint = getattr(route, "path", "") or ""
                client = self.client if self.client is not None else scope["app"].state.opspilot
                client.report_exception(exc, endpoint=endpoint,
                                        metadata={"source": "fastapi"})
            except Exception:
                pass
            raise
