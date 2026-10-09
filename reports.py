

import httpx

from database import SessionLocal
from models import Orders

failed_url="https://countries.dev/this-endpoint-does-not-exist"

succes_url= "https://countries.dev/alpha/IN"

def generate_sales_report(attempt:int):

    db=SessionLocal()

    try:
        orders=db.query(Orders).all()
        total_orders = len(orders)
        total_revenue = sum(order.amount for order in orders)

        average_order_value = (
            total_revenue / total_orders
            if total_orders > 0
            else 0
        )

        if attempt==1:
            response = httpx.get(
                        failed_url,
                        timeout=5.0
                    )
        else:

            response = httpx.get(
                succes_url,
                timeout=5.0
                )

        response.raise_for_status() #raises an exception if the API returns an HTTP error status.
        country_data = response.json()

        return {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "average_order_value": average_order_value,
            "country": country_data
        }

    
    
    finally:
        db.close()


#Currently, the flow is:
#Job queued
#     ↓
# Worker calls API
#     ↓
# API returns 404
#     ↓
# Job marked failed ❌

# We want:

# Job queued
#     ↓
# Attempt 1 → fails
#     ↓
# Attempt 2 → fails
#     ↓
# Attempt 3 → succeeds
#     ↓
# Job completed ✅. We'll allow 3 total attempts: the original request plus 2 retries.