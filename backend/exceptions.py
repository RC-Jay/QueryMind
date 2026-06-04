"""
Domain exceptions — raised by the service layer, translated to HTTP responses
by a single central handler registered in main.py.

Services raise these instead of fastapi.HTTPException, keeping business logic
free of any web-framework knowledge.
"""


class AppError(Exception):
    """Base class for all domain errors. Carries the HTTP status to map to."""
    status_code: int = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ValidationError(AppError):
    status_code = 400


class AuthError(AppError):
    status_code = 401


class InvalidTokenError(AuthError):
    """A JWT was malformed, expired, or of the wrong type."""


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ServiceUnavailableError(AppError):
    status_code = 503
