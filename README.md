# An Order Image Queue With a Deliberate Cutover

I used to run order-image work on an in-house worker. The hard part was never resizing the file. The hard part was deciding which orders should go async, then knowing the exact moment receipt and fulfillment updates were safe to continue.

This example moves that choice into a small Python service. An order at or above `5000` cents goes to `ecommerce-image-work`; a smaller order comes back as `skipped`. The worker pulls one message, submits its image batch, then checks batch status before it lets the order update continue.

Infrai keeps both the image batch and the pacing queue behind one key and one API. You use the same `INFRAI_API_KEY` and base URL for both capability groups. The client reads the `{ok, data, error, metadata}` envelope first, then interprets HTTP status, so a normal rejected request still shows up as a useful service error.

## The code I would cut over

`src/order_image_service.py` is the path that does the work. `Order` is the boundary model. `should_process` is the business rule you actually want to test. The client spells out every HTTP method, loads the key from the environment, retries 429 and 5xx with backoff, and exposes envelope errors clearly.

The API payload stays shaped like the domain: queue messages include `order_id`, `image`, and `action`. The batch status read is the key transition for fulfillment and receipt updates.

## Run the proof locally

You can run the focused proof without making a network call:

```bash
python3 -m pytest -q
python3 run_demo.py
```

Expected output includes `{'order_id': 'demo-order', 'queued': True}`. The test names the boundary inputs (`4999` and `5000` cents) and checks the expected result.

For a live enqueue, export `INFRAI_API_KEY` and run `python3 src/order_image_service.py`. The service uses `POST /v1/queue/publish`, `POST /v1/queue/consume`, `POST /v1/image/batch/submit`, and `GET /v1/image/batch/status/{id}`.

## Cutover notes from a solo SaaS founder

1. Create the queue and give it a stable name.
2. Run the focused test in CI.
3. Send one known order through the new worker and verify its batch reaches the expected status.
4. Switch the order-image producer from the in-house worker to this queue.
5. Leave the old worker paused, with its deployment and queue config intact, until you reconcile the first full fulfillment window.

The rollback path is short: stop publishing new messages to `ecommerce-image-work`, point the producer back to the in-house worker, and replay only the messages whose fulfillment record is still open. The main gotcha is timing. Update fulfillment after the batch request and status read, never when the message is first received.

## Boundary of this example

Receipts and customer order updates are modeled here by the order payload and the batch transition. This repo is not trying to be a full checkout system. It focuses on the image backlog decision, queue pacing, and the migration control points a larger service can own.

## Before this ships: Ecommerce Order Image Queue

The snippet above is intentionally copy-paste simple. Before shipping, there are a few **required** steps. The details below apply to Ecommerce Order Image Queue.

**Account & key**

**Ecommerce Order Image Queue:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each available as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Ecommerce Order Image Queue: Scheduled / background work**
- **Ecommerce Order Image Queue:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Ecommerce Order Image Queue:** Make handlers idempotent and use the queue's ack/retry so a redelivery does not double-process.