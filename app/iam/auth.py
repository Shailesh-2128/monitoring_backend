import jwt
import datetime
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from app.iam.models import UserProfile

JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DAYS = 7

def generate_jwt_token(user: User) -> str:
    """Generate JWT token for a given user."""
    profile = getattr(user, 'profile', None)
    is_superadmin = profile.is_superadmin if profile else user.is_superuser
    
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'is_superadmin': is_superadmin,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=JWT_EXPIRATION_DAYS),
        'iat': datetime.datetime.now(datetime.timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> dict:
    """Decode JWT token and return payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed('Token has expired.')
    except jwt.InvalidTokenError:
        raise AuthenticationFailed('Invalid token.')

class JWTAuthentication(BaseAuthentication):
    """Custom DRF Authentication backend using JWT tokens."""

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2:
            return None

        prefix, token = parts[0], parts[1]
        if prefix.lower() not in ['bearer', 'token']:
            return None

        payload = decode_jwt_token(token)
        user_id = payload.get('user_id')
        if not user_id:
            raise AuthenticationFailed('Invalid token payload.')

        try:
            user = User.objects.select_related('profile', 'profile__role', 'profile__team').get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found.')

        if not user.is_active:
            raise AuthenticationFailed('User account is deactivated.')

        return (user, token)
