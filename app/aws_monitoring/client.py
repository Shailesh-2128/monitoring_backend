try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception
    BOTO3_AVAILABLE = False

from .exceptions import (
    AWSAuthenticationError,
    AWSPermissionDeniedError,
    AWSRateLimitError,
    AWSServiceError
)


class AWSClient:
    def __init__(self, access_key_id: str, secret_access_key: str, region_name: str = 'ap-south-1'):
        self.access_key_id = access_key_id.strip() if access_key_id else ""
        self.secret_access_key = secret_access_key.strip() if secret_access_key else ""
        self.region_name = region_name.strip() if region_name else "ap-south-1"
        self._session = None
        self._clients = {}

    def get_session(self):
        if not BOTO3_AVAILABLE:
            raise AWSAuthenticationError("boto3 Python package is required. Please install via: pip install boto3 botocore")
        if not self._session:
            if not self.access_key_id or not self.secret_access_key:
                raise AWSAuthenticationError("Missing AWS Access Key ID or Secret Access Key")
            self._session = boto3.session.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name
            )
        return self._session

    def get_client(self, service_name: str):
        if service_name not in self._clients:
            session = self.get_session()
            try:
                self._clients[service_name] = session.client(service_name)
            except Exception as e:
                self.handle_boto_exception(e, service_name)
        return self._clients[service_name]

    def verify_credentials(self) -> dict:
        """Calls STS get_caller_identity() to verify AWS credentials and region."""
        try:
            sts = self.get_client('sts')
            identity = sts.get_caller_identity()
            return {
                'account': identity.get('Account'),
                'arn': identity.get('Arn'),
                'user_id': identity.get('UserId'),
                'region': self.region_name
            }
        except Exception as e:
            self.handle_boto_exception(e, 'sts')

    def handle_boto_exception(self, exc: Exception, service_name: str = "AWS"):
        if isinstance(exc, AWSMonitoringBaseException):
            raise exc
        if isinstance(exc, ClientError):
            code = exc.response.get('Error', {}).get('Code', '')
            msg = exc.response.get('Error', {}).get('Message', str(exc))

            if code in ['AuthFailure', 'InvalidAccessKeyId', 'SignatureDoesNotMatch', 'UnrecognizedClientException']:
                raise AWSAuthenticationError(f"AWS Authentication Failed ({code}): {msg}")
            elif code in ['AccessDenied', 'UnauthorizedOperation', 'AccessDeniedException']:
                raise AWSPermissionDeniedError(f"AWS Permission Denied ({code}) for {service_name}: {msg}")
            elif code in ['RequestLimitExceeded', 'Throttling', 'ThrottlingException', 'ProvisionedThroughputExceededException']:
                raise AWSRateLimitError(f"AWS Rate Limit Exceeded ({code}): {msg}")
            else:
                raise AWSServiceError(f"AWS {service_name} Error ({code}): {msg}")
        elif isinstance(exc, BotoCoreError):
            raise AWSServiceError(f"AWS BotoCore Error: {str(exc)}")
        else:
            raise AWSServiceError(f"AWS {service_name} Error: {str(exc)}")

