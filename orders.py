
from itertools import product
import json
from uuid import uuid4

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from database import get_db
from models import Orders
from redis_client import redis_client


class OrderCreate(BaseModel):
    product: str
    amount: int
    status: str

class OrderUpdate(BaseModel):
    status: str

class ReportRequest(BaseModel):
    report_type: str


router=APIRouter(
    prefix='/orders',
    tags=['orders']
)


@router.post("/reports")
def create_report(request: ReportRequest):
    job_id=str(uuid4())
    job = {
        "job_id": job_id,
        "report_type": request.report_type
    }

    redis_client.set(
        f"job:{job_id}",
        json.dumps({
            "job_id": job_id,
            "report_type": request.report_type,
            "status": "queued"
        })
    )

    redis_client.lpush("report_jobs", json.dumps(job))

    return {
        "job_id": job_id,
        "status": "queued"
    }

@router.get("/reports/jobs/{job_id}")
def get_job_status(job_id: str):
    job = redis_client.get(f"job:{job_id}")
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return json.loads(job)

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



