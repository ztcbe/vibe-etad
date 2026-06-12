from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": self.details})


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found"):
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, code: str = "CONFLICT", message: str = "Resource already exists"):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "Authentication required"):
        super().__init__(code=code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "Permission denied"):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)


class ValidationError(AppError):
    def __init__(self, code: str = "VALIDATION_ERROR", message: str = "Invalid input", details: dict | None = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, details=details)


def standard_response(data=None, error=None, meta=None):
    return {
        "success": error is None,
        "data": data,
        "error": error,
        "meta": meta or {},
    }
