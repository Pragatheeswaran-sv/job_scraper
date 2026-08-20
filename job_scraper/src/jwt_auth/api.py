from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.config import get_logger
from src.database import get_db
from src.services.jwt_auth.dependancy import get_current_user, require_role
from src.jwt_auth.schema import (
    APIResponse,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
)
from src.services.jwt_auth.service import (
    authenticate_user,
    create_tokens,
    refresh_access_token,
    revoke_refresh_token,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/profile")
def get_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        return {
            "status_code": status.HTTP_200_OK,
            "message": "User information retrieved successfully",
            "data": {
                "user_id": current_user.get("sub"),
                "email": current_user.get("email"),
                "role": current_user.get("role"),
            },
        }
    except Exception as e:
        logger.exception("Error retrieving user profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/login", response_model=APIResponse[TokenResponse])
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(
            db=db,
            email_address=login_data.email_address,
            password=login_data.password,
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email address or password",
            )

        access_token, refresh_token = create_tokens(db=db, user=user)
        logger.info("User logged in: %s", login_data.email_address)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "login successfully",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during login for: %s", login_data.email_address)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/refresh", response_model=APIResponse[dict])
def refresh_token(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        access_token = refresh_access_token(
            db=db,
            refresh_token=refresh_data.refresh_token,
        )

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        logger.info("Access token refreshed")
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Access token refreshed successfully",
            "data": {
                "access_token": access_token,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error refreshing access token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/logout")
def logout(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        revoked = revoke_refresh_token(
            db=db,
            refresh_token=refresh_data.refresh_token,
        )

        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or already revoked refresh token",
            )

        logger.info("User logged out")
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Logout successfully",
            "data": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during logout")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/admin/profile")
def admin_profile(
    current_user: dict[str, Any] = Depends(require_role("admin")),
):
    try:
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Admin profile retrieved successfully",
            "data": {
                "user_id": current_user.get("sub"),
                "email": current_user.get("email"),
                "role": current_user.get("role"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error accessing admin profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/user/profile")
def user_profile(
    current_user: dict[str, Any] = Depends(require_role("user")),
):
    try:
        return {
            "status_code": status.HTTP_200_OK,
            "message": "User profile retrieved successfully",
            "data": {
                "user_id": current_user.get("sub"),
                "email": current_user.get("email"),
                "role": current_user.get("role"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error accessing user profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
