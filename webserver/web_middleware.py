from starlette.types import ASGIApp, Receive, Scope, Send


# ========== custom exceptions ==========

class FilesSizeTooLargeError(Exception):
    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size




# ========== middleware logics =========

# ignore large-content requests
class SizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_size: int):
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        content_length = 0
        for header, value in headers:
            if header.lower() == b'content-length':
                try:
                    content_length = int(value)
                except ValueError:
                     pass
                break

        if content_length > self.max_size:
             raise FilesSizeTooLargeError(size=content_length, max_size=self.max_size)

        await self.app(scope, receive, send)