class AppError(Exception):
    status_code = 400
    code = 'invalid_request'

    def __init__(self, message: str, *, trace_id: str | None=None):
        super().__init__(message)
        self.trace_id = trace_id

class Conflict(AppError):
    status_code = 409
    code = 'version_conflict'

class NotFound(AppError):
    status_code = 404
    code = 'not_found'

class Forbidden(AppError):
    status_code = 403
    code = 'forbidden'

class ProviderError(AppError):
    status_code = 502
    code = 'provider_error'

class ConfigurationError(AppError):
    status_code = 503
    code = 'configuration_error'
