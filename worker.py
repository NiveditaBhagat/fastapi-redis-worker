print("THIS IS THE NEW WORKER")
import json
import time
from redis_client import redis_client
from reports import generate_sales_report


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





# Failure → delayed_jobs (sorted set)
#                     ↓
#               Wait until due
#                     ↓
#               report_jobs
#                     ↓
#                   Worker