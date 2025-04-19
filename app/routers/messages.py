from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/messages",
    tags=["messages"],
    responses={404: {"description": "Message not found"}},
)

@router.post("/", response_model=schemas.Message, status_code=status.HTTP_201_CREATED)
def create_message(message: schemas.MessageCreate, db: Session = Depends(get_db)):
    """
    Отправить сообщение.
    
    - Если is_broadcast=True, то recipient_id игнорируется и сообщение отправляется всем водителям
    - Если is_broadcast=False, то recipient_id должен быть указан и сообщение отправляется конкретному водителю
    """
    if not message.is_broadcast and message.recipient_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipient ID must be provided for non-broadcast messages"
        )
    
    if message.recipient_id:
        # Проверяем, существует ли получатель
        db_driver = crud.get_driver(db, driver_id=message.recipient_id)
        if db_driver is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient driver not found"
            )
    
    return crud.create_message(db=db, message=message)

@router.post("/bulk", response_model=List[schemas.Message], status_code=status.HTTP_201_CREATED)
def create_bulk_messages(recipient_ids: List[int], content: str, db: Session = Depends(get_db)):
    """
    Отправить сообщение нескольким получателям одновременно.
    
    Принимает список ID водителей и текст сообщения.
    """
    messages = []
    
    for recipient_id in recipient_ids:
        # Проверяем, существует ли получатель
        db_driver = crud.get_driver(db, driver_id=recipient_id)
        if db_driver is None:
            continue  # Пропускаем несуществующих водителей
        
        message = schemas.MessageCreate(
            content=content,
            is_broadcast=False,
            recipient_id=recipient_id
        )
        
        messages.append(crud.create_message(db=db, message=message))
    
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid recipients found"
        )
    
    return messages

@router.get("/driver/{driver_id}", response_model=List[schemas.Message])
def read_driver_messages(driver_id: int, db: Session = Depends(get_db)):
    """Получить все сообщения для конкретного водителя (персональные + общие рассылки)"""
    # Проверяем, существует ли водитель
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    return crud.get_messages_for_driver(db, driver_id=driver_id)

@router.get("/broadcast", response_model=List[schemas.Message])
def read_broadcast_messages(db: Session = Depends(get_db)):
    """Получить все общие рассылки"""
    return crud.get_broadcast_messages(db) 