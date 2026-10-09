# A. report_jobs — the ready queue
# Jobs that are ready to run now. Your worker already reads from this list using BRPOP.
# Sales report A — ready
# Sales report B — ready


# Scheduler moves jobs when they're due

# B. delayed_jobs — the waiting area
# Jobs that should run later. Each job gets a score representing its scheduled Unix timestamp.
# Retry job A  Due in 5 sec
# Retry job B  Due in 20 sec
# This is a separate process whose job is to check whether delayed jobs are ready to run.

print("schedular running")
import json
import time
from redis_client import redis_client


while True:

    now=time.time()
    due_jobs = redis_client.zrangebyscore(
        "delayed_jobs",
        min="-inf",
        max=now
    ) #Finds jobs whose score is less than or equal to the current timestamp. Those jobs are due.

    for job_json in due_jobs:
        # Remove the job from the delayed set.
        # Only enqueue it if removal succeeds.
        removed = redis_client.zrem("delayed_jobs", job_json)

        if removed:
            redis_client.lpush("report_jobs", job_json)
            print("Moved delayed job to ready queue:", job_json)

    time.sleep(1)



# POST /reports
#      |
#      v
# FastAPI creates job_id
#      |
#      v
# Redis stores status = queued
#      |
#      v
# Redis ready queue: report_jobs
#      |
#      v
# Worker picks up the job
#      |
#      v
# Attempt 1: API returns 404
#      |
#      v
# Redis delayed queue: delayed_jobs
#      |
#      v
# Scheduler waits until retry time
#      |
#      v
# Job moves back to report_jobs
#      |
#      v
# Worker runs attempt 2
#      |
#      v
# API succeeds + database report generated
#      |
#      v
# Redis stores status = completed