print("THIS IS THE NEW WORKER")
import json
import time
from redis_client import redis_client
from reports import generate_sales_report
import httpx


def save_webhook_delivery(delivery_id, payload):
    delivery = {
        "delivery_id": delivery_id,
        "payload": payload,
        "status": "pending",
        "attempts": 0,
    }

    redis_client.set(
        f"webhook_delivery:{delivery_id}",
        json.dumps(delivery),
    )

    print(f"Saved webhook delivery record: {delivery_id}")


def send_webhook(job_id, event, status, result=None):
    payload = {
        "event": event,
        "job_id": job_id,
        "status": status,
        "result": result,
    }
    save_webhook_delivery(job_id, payload)
    max_attempts = 4

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"Sending webhook for job {job_id} "
                f"(attempt {attempt}/{max_attempts})"
            )

            response = httpx.post(
                "http://localhost:8001/webhook",
                json=payload,
                timeout=5.0,
            )

            # Treat HTTP error responses (4xx/5xx) as failures.
            response.raise_for_status()

            delivery_key = f"webhook_delivery:{job_id}"
            delivery = json.loads(redis_client.get(delivery_key))

            delivery["status"] = "delivered" 
            delivery["attempts"] = attempt

            redis_client.set( delivery_key, json.dumps(delivery), )

            print(f"Webhook delivered for job {job_id}")
            return True

        except httpx.HTTPError as error:
            print(f"Webhook attempt {attempt} failed: {error}")

            if attempt == max_attempts:

                delivery_key = f"webhook_delivery:{job_id}" 
                saved_delivery = redis_client.get(delivery_key)

                if saved_delivery: 
                    delivery = json.loads(saved_delivery) 
                    delivery["status"] = "pending_retry" 
                    delivery["attempts"] = attempt 
                    delivery["next_retry_at"] = time.time() + 30
                    redis_client.set( delivery_key, json.dumps(delivery), ) 
                    print( f"Webhook delivery failed after " f"{max_attempts} attempts" ) 
                    return False

            wait_time = 2 ** (attempt - 1)

            print(
                f"Retrying webhook in {wait_time} second(s)..."
            )

            time.sleep(wait_time)


def recover_pending_webhooks():
    current_time = time.time()

    for key in redis_client.scan_iter(match="webhook_delivery:*"):
        saved_delivery = redis_client.get(key)

        if not saved_delivery:
            continue

        delivery = json.loads(saved_delivery)

        # Only recover deliveries that previously failed.
        if delivery["status"] != "pending_retry":
            continue

        # Wait until the scheduled retry time.
        next_retry_at = delivery.get("next_retry_at", 0)

        if current_time < next_retry_at:
            continue

        delivery_id = delivery["delivery_id"]
        payload = delivery["payload"]

        print(f"Recovering webhook delivery: {delivery_id}")

        try:
            response = httpx.post(
                "http://localhost:8001/webhook",
                json=payload,
                timeout=5.0,
            )
            response.raise_for_status()

            delivery["status"] = "delivered"
            delivery["attempts"] += 1
            delivery.pop("next_retry_at", None)

            redis_client.set(key, json.dumps(delivery))

            print(f"Recovered webhook delivery: {delivery_id}")

        except httpx.HTTPError as error:
            delivery["attempts"] += 1

            # Maximum total attempts, including initial delivery attempts.
            max_attempts = 7

            if delivery["attempts"] >= max_attempts:
                delivery["status"] = "failed"
                delivery.pop("next_retry_at", None)

                print(
                    f"Webhook delivery permanently failed for "
                    f"{delivery_id} after {delivery['attempts']} attempts: "
                    f"{error}"
                )
            else:
                delivery["status"] = "pending_retry"
                delivery["next_retry_at"] = time.time() + 60

                print(
                    f"Recovery failed for {delivery_id}: {error}. "
                    f"Retrying in 60 seconds."
                )

            redis_client.set(key, json.dumps(delivery))


while True:
    job = redis_client.brpop("report_jobs", timeout=5)

    if job:
        print("Got job:", job)
       
        job_data = json.loads(job[1])

        job_id = job_data["job_id"]
        report_type = job_data["report_type"]
        attempt = job_data.get("attempt", 1)

        print("Job ID:", job_id)
        print("Job type:", report_type)

        redis_client.set(
            f"job:{job_id}",
            json.dumps({
                "job_id": job_id,
                "report_type": report_type,
                "status": "processing"
            })
        )

        if report_type == "sales":
            try:

                result = generate_sales_report(attempt=attempt)
            
                redis_client.set(
                    f"job:{job_id}",
                    json.dumps({
                        "job_id": job_id,
                        "report_type": report_type,
                        "status": "completed",
                         "attempt": attempt,
                        "result": result
                    })
                 )
                print("Generating sales report...")

                send_webhook(
                    job_id=job_id,
                    event="report.completed",
                    status="completed",
                    result= result,
                )

            except Exception as e:
                print(f"Attempt {attempt} failed:", e)

                if attempt < 3:

                    next_attempt = attempt + 1
                    job_data["attempt"] = next_attempt

                    wait_time = 2 ** (attempt - 1)
                    print(f"Waiting {wait_time} seconds before retry...")

                    run_at = time.time() + wait_time
                    #time.sleep(wait_time)
                    #time.sleep() pauses the entire worker process.
                    # That's okay for learning with one worker, but production systems often schedule delayed retries without making a worker sit idle.

                   


                    redis_client.set(
                        f"job:{job_id}",
                        json.dumps({
                            "job_id": job_id,
                            "report_type": report_type,
                            "status": "queued",
                            "attempt": next_attempt,
                            "retry_at": run_at
                         })
                        )

                    # redis_client.lpush(
                    #     "report_jobs",
                    #      json.dumps(job_data)
                    #     )

                   
                    redis_client.zadd(
                            "delayed_jobs",
                             {json.dumps(job_data): run_at}
                        )
                    print(
                        f"Retry scheduled for attempt {next_attempt} "
                        f"in {wait_time} seconds"
                    )
                   
                else:
                    redis_client.set(
                        f"job:{job_id}",
                        json.dumps({
                            "job_id": job_id,
                            "report_type": report_type,
                            "status": "failed",
                            "attempt": attempt,
                            "error": str(e)
                        })
                        )

                    print("Maximum attempts reached. Job failed.")
                    send_webhook(
                        job_id=job_id,
                        event="report.failed",
                        status="failed",
                        result={"error": str(e)},
                        )
    recover_pending_webhooks()




# Failure → delayed_jobs (sorted set)
#                     ↓
#               Wait until due
#                     ↓
#               report_jobs
#                     ↓
#                   Worker