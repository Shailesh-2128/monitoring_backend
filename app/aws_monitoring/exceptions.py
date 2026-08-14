class AWSMonitoringBaseException(Exception):
    """Base exception for AWS Monitoring operations."""
    def __init__(self, message="AWS Monitoring Exception occurred", status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AWSAuthenticationError(AWSMonitoringBaseException):
    """Raised when AWS Access Key ID or Secret Access Key is invalid or expired."""
    def __init__(self, message="Invalid AWS Credentials or STS identity verification failed"):
        super().__init__(message=message, status_code=401)


class AWSPermissionDeniedError(AWSMonitoringBaseException):
    """Raised when IAM permissions (e.g. ec2:DescribeInstances, ce:GetCostAndUsage) are missing."""
    def __init__(self, message="IAM permission denied for this AWS action"):
        super().__init__(message=message, status_code=403)


class AWSRateLimitError(AWSMonitoringBaseException):
    """Raised when AWS API rate limits or throttling occurs."""
    def __init__(self, message="AWS API rate limit exceeded. Retrying shortly."):
        super().__init__(message=message, status_code=429)


class AWSServiceError(AWSMonitoringBaseException):
    """Raised when an AWS service call fails."""
    def __init__(self, message="AWS Service request failed"):
        super().__init__(message=message, status_code=500)
