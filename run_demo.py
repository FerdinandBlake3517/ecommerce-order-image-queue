from src.order_image_service import Order, should_process


order = Order("demo-order", 7500, "catalog/demo.jpg")
print({"order_id": order.order_id, "queued": should_process(order)})
