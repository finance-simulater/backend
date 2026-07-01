from app.api.v1.auth.schema import LoginRequest, TokenResponse
from app.core.security import create_access_token


class AuthService:
    def login(self, login_request: LoginRequest) -> TokenResponse:
        token = create_access_token(subject=login_request.username)
        return TokenResponse(access_token=token)
