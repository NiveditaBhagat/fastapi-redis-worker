print("THIS IS THE NEW WORKER")
import json

from redis_client import redis_client
from reports import generate_sales_report


while True:
    job = redis_client.brpop("report_jobs", timeout=5)

    if job:
        print("Got job:", job)
       
        job_data = json.loads(job[1])

        job_id = job_data["job_id"]
        report_type = job_data["report_type"]

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
            result = generate_sales_report()
            
            redis_client.set(
                f"job:{job_id}",
                json.dumps({
                    "job_id": job_id,
                    "report_type": report_type,
                    "status": "completed",
                    "result": result
                })
            )
            print("Generating sales report...")