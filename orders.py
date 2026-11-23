
from itertools import product
import json
from uuid import uuid4
from fastapi import Query, Request
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from rate_limit import check_rate_limit
from database import get_db
from models import Orders
from redis_client import redis_client
from fastapi import Header

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



CREATE_JOB_SCRIPT = """
local existing = redis.call("GET", KEYS[1])

if existing then
    local saved = cjson.decode(existing)

    if saved.report_type ~= ARGV[2] then
        return {-1, saved.job_id}
    end

    return {0, saved.job_id}
end

local mapping = cjson.encode({
    job_id = ARGV[1],
    report_type = ARGV[2]
})

local job = cjson.encode({
    job_id = ARGV[1],
    report_type = ARGV[2],
    status = "queued"
})

redis.call("SET", KEYS[1], mapping, "EX", ARGV[4])
redis.call("SET", KEYS[2], job)
redis.call("LPUSH", KEYS[3], ARGV[3])

return {1, ARGV[1]}
"""


@router.post("/reports")
def create_report(
    report_request: ReportRequest,
    request: Request,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key"
    ),
):
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key cannot be empty"
        )

    mapping_key = f"idempotency:mapping:{idempotency_key}"

    # 1. Fast path: check for a previous request.
    existing = redis_client.get(mapping_key)

    if existing:
        saved = json.loads(existing)

        if saved["report_type"] != report_request.report_type:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used "
                       "for a different report type."
            )

        job = redis_client.get(f"job:{saved['job_id']}")

        if not job:
            raise HTTPException(
                status_code=500,
                detail="Job record is missing."
            )

        return json.loads(job)

    # 2. Rate-limit new requests.
    client_id = (
        request.client.host
        if request.client
        else "unknown"
    )

    allowed, retry_after = check_rate_limit(client_id)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Prepare the new job.
    job_id = str(uuid4())

    queue_payload = json.dumps({
        "job_id": job_id,
        "report_type": report_request.report_type
    })

    # 4. Atomically check, save and enqueue.
    result = redis_client.eval(
        CREATE_JOB_SCRIPT,
        3,
        mapping_key,
        f"job:{job_id}",
        "report_jobs",
        job_id,
        report_request.report_type,
        queue_payload,
        86400,
    )

    outcome = int(result[0])
    actual_job_id = (
        result[1].decode()
        if isinstance(result[1], bytes)
        else result[1]
    )

    # -1 means the key was reused with a different report type.
    if outcome == -1:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used "
                   "for a different report type."
        )

    # 0 means another request already created this job.
    # 1 means this request created it.
    job = redis_client.get(f"job:{actual_job_id}")

    if not job:
        raise HTTPException(
            status_code=500,
            detail="Job record is missing."
        )

    return json.loads(job)



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
def get_orders(page: int = Query(1, ge=1),
               limit: int = Query(10, ge=1, le=100),
               db: Session = Depends(get_db)):

    offset = (page - 1) * limit

    order=db.query(Orders).offset(offset).limit(limit).all()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")


    return {
        "page": page,
        "limit": limit,
        "orders": order,
    }

@router.get("/cursor")
def get_orders_cursor(
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=5, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Orders)

    # Start after the last order from the previous page.
    if cursor is not None:
        query = query.filter(Orders.id > cursor)

    # Fetch one extra order to check whether more results exist.
    orders = (
        query
        .order_by(Orders.id.asc())
        .limit(limit + 1)
        .all()
    )

    has_more = len(orders) > limit

    # Remove the extra order if one was fetched.
    orders = orders[:limit]

    # Use the last returned order as the next cursor.
    next_cursor = orders[-1].id if orders and has_more else None

    return {
        "orders": [
            {
                "id": order.id,
                "product": order.product,
                "amount": order.amount,
                "status": order.status,
            }
            for order in orders
        ],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }

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



