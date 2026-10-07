

from database import SessionLocal
from models import Orders


def generate_sales_report():

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

        return {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "average_order_value": average_order_value
        }
    finally:
        db.close()
