class AppError(Exception):
    def __init__(self, status: int, message: str, details=None):
        self.status, self.message, self.details = status, message, details


def require(condition, message, status=422):
    if not condition:
        raise AppError(status, message)
