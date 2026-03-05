class AiradarError(Exception):
    """Base error for the tool."""


class ConfigurationError(AiradarError):
    pass


class NoSerpResultsError(AiradarError):
    pass


class UpstreamApiError(AiradarError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class DeepSeekInsufficientBalanceError(UpstreamApiError):
    pass


class InvalidModelJsonError(AiradarError):
    pass


class FirecrawlTimeoutError(AiradarError):
    pass

