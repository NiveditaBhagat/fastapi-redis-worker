
from itertools import product

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from database import get_db
from models import Orders


class OrderCreate(BaseModel):
    product: str
    amount: int
    status: str

class OrderUpdate(BaseModel):
    status: str


router=APIRouter(
    prefix='/orders',
    tags=['orders']
)


@router.get("/all")
def get_orders(db: Session = Depends(get_db)):
    order=db.query(Orders).all()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")


    return order



@router.post("/orders")
def create_order(order_data: OrderCreate,db: Session = Depends(get_db)):
    order=Orders(
        product=order_data.product,
        amount=order_data.amount,
        status=order_data.status
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order

@router.patch("/orders/{order_id}")
def update_order(order_id:int, order_update:OrderUpdate,db: Session = Depends(get_db)):
     
    order=db.query(Orders).filter(Orders.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = order_update.status

    db.commit()
    db.refresh(order)

    return order



