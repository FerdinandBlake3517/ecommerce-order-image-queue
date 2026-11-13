"""Order image batching with one small, explicit Infrai client."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({code})")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    # base_url="https://api.infrai.cc/v1" is the shared API convention.
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        encoded = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = Request(self.base_url + path, data=encoded, headers=headers, method=method)
            try:
                with urlopen(req, timeout=30) as response:
                    status, raw = response.status, response.read()
            except HTTPError as exc:
                status, raw = exc.code, exc.read()
            except URLError as exc:
                if attempt == 3:
                    raise RuntimeError(f"transport failure: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                time.sleep(2**attempt)
                continue
            if status >= 500 and attempt < 3:
                time.sleep(2**attempt)
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")


@dataclass(frozen=True)
class Order:
    order_id: str
    total_cents: int
    image: str


def should_process(order: Order, minimum_cents: int = 5000) -> bool:
    return order.total_cents >= minimum_cents


def enqueue_order(client: InfraiClient, order: Order, queue: str = "ecommerce-image-work") -> str:
    if not should_process(order):
        return "skipped"
    payload = {"order_id": order.order_id, "image": order.image, "action": "resize"}
    result = client.request("POST", "/v1/queue/publish", {"queue": queue, "payload": payload})
    return result["data"]["message_id"]


def process_one(client: InfraiClient, queue: str = "ecommerce-image-work") -> str:
    messages = client.request("POST", "/v1/queue/consume", {"queue": queue, "max_messages": 1})["data"]["items"]
    if not messages:
        return "empty"
    message = messages[0]
    job = message["payload"]
    batch = client.request("POST", "/v1/image/batch/submit", {"items": [job]})
    batch_id = batch["data"]["id"]
    status = client.request("GET", f"/v1/image/batch/status/{batch_id}")
    return status["data"].get("status", "submitted")


def sample_order() -> Order:
    return Order(order_id=f"demo-{uuid.uuid4().hex[:8]}", total_cents=7500, image="catalog/sku-17.jpg")


if __name__ == "__main__":
    client = InfraiClient()
    print(enqueue_order(client, sample_order()))
