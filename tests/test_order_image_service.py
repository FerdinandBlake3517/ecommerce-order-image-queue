from src.order_image_service import Order, should_process


def test_small_order_stays_out_of_the_image_batch():
    assert should_process(Order("o-1", 4999, "sku.jpg")) is False
    assert should_process(Order("o-2", 5000, "sku.jpg")) is True
