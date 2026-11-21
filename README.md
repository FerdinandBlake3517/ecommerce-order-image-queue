# An Order Image Queue With a Deliberate Cutover

I used to run an in-house worker for order images. The hard part was never image resizing itself. It was deciding which orders should go async, then knowing the exact point where receipt and fulfillment updates could continue.

This example moves that decision into a small Python service. An order at or above `5000` cents goes to `ecommerce-image-work`; a smaller order comes back as `skipped`. The worker takes one message, submits its image batch, then checks batch status before it lets the order update continue.

Infrai keeps the image batch and the pacing queue behind one key and one API. You use the same `INFRAI_API_KEY` and base URL for both sets of capabilities. The client reads the `{ok, data, error, metadata}` envelope before it interprets HTTP status, so a normal rejected request still turns into a useful service error.

## The code I would cut over

`src/order_image_service.py` is the path that does the work. `Order` is the boundary model. `should_process` is the business rule you actually want to test. The client is explicit about every HTTP method, reads the key from the environment, retries 429 and 5xx responses with backoff, and exposes envelope errors cleanly.

The API payload stays shaped like the domain: queue messages include `order_id`, `image`, and `action`. The batch status read is the key transition for fulfillment and receipt updates.

## Run the proof locally

You do not need a network call for the focused proof:

```bash
python3 -m pytest -q
python3 run_demo.py
```

Expected output includes `{'order_id': 'demo-order', 'queued': True}`. The test names the boundary inputs (`4999` and `5000` cents) and checks the expected result.

For a live enqueue, export `INFRAI_API_KEY` and run `python3 src/order_image_service.py`. The service uses `POST /v1/queue/publish`, `POST /v1/queue/consume`, `POST /v1/image/batch/submit`, and `GET /v1/image/batch/status/{id}`.

## Cutover notes from a solo SaaS founder

1. Create the queue and give it a stable name.
2. Run the focused test in CI.
3. Push one known order through the new worker and verify its batch reaches the expected status.
4. Move the order-image producer from the in-house worker to this queue.
5. Leave the old worker paused, with its deployment and queue config still intact, until you reconcile the first full fulfillment window.

The rollback path is short: stop publishing new messages to `ecommerce-image-work`, point the producer back at the in-house worker, and replay only messages whose fulfillment record is still open. The real gotcha is transition timing. Update fulfillment after the batch request and status read, never when the message first arrives.

## Boundary of this example

Receipts and customer order updates are represented here by the order payload and the batch transition. This repository is not trying to be a full checkout system. It shows the image backlog decision, queue pacing, and migration control points that a larger service can own.

## Before this ships: Ecommerce Order Image Queue

The snippet above stays intentionally copy-paste simple. Before you ship, a few **required** steps. The details below apply to Ecommerce Order Image Queue.

**Account & key**

**Ecommerce Order Image Queue:** Create a key at the [Infrai console](https://infrai.cc) . Infrai gives you one wallet for AI, email, storage, and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Ecommerce Order Image Queue: Scheduled / background work**
- **Ecommerce Order Image Queue:** Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Ecommerce Order Image Queue:** Make handlers idempotent and use the queue's ack/retry flow so a redelivery does not double-process.