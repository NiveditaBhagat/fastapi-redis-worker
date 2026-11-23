
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class WebhookEvent(BaseModel):
    event: str
    job_id: str
    status: str
    result: dict[str, Any] | None = None


@app.post("/webhook")
def receive_webhook(payload: WebhookEvent):
    print("Webhook received!")
    print(f"Event: {payload.event}")
    print(f"Job ID: {payload.job_id}")
    print(f"Status: {payload.status}")
    print(f"Result: {payload.result}")

    return {
        "message": "Webhook received successfully",
        "job_id": payload.job_id
    }