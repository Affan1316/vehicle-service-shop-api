class ServiceError(Exception):
    """Base exception for all service layer errors."""
    pass


class NotFoundError(ServiceError):
    """Exception raised when a requested resource is not found."""
    pass


class ValidationError(ServiceError):
    """Exception raised when input data fails service-level business rules."""
    pass


class PaymentGatewayError(ServiceError):
    """Exception raised when payment processor integration fails or is unconfigured."""
    pass
