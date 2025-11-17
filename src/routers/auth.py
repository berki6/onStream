from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from src.schema import schemas
from src.services import crud
from src.core.database import get_db
from src.core.auth import verify_password, create_access_token
from src.core.config import settings
from src.core.logger import get_logger
from datetime import datetime, timezone

router = APIRouter()

logger = get_logger(__name__)


@router.post(
    "/register", response_model=schemas.APIResponse, status_code=status.HTTP_201_CREATED
)
def register_user(
    request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)
):
    # Check if username already exists
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user
    new_user = crud.create_user(db, user)
    logger.info(f"User '{user.username}' registered successfully with request_id={request.state.request_id}")

    return schemas.APIResponse(
        data=new_user,
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="User registered successfully",
    )


@router.post("/login", response_model=schemas.APIResponse)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"User '{form_data.username}' logged in successfully with request_id={request.state.request_id}")

    return schemas.APIResponse(
        data={"access_token": access_token, "token_type": "bearer"},
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Login successful",
    )
