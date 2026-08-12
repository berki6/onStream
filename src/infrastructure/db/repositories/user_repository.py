from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.core.security.passwords import get_password_hash
from src.infrastructure.db import models
from src import schemas

logger = get_logger(__name__)


def get_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def create(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Created user: {user.username}")
    return db_user
