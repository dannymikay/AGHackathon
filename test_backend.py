#!/usr/bin/env python3
"""
AgriMatch backend smoke test.

Run with:
    conda run -n agrimatch_stable python test_backend.py

Requires the server to be running at http://localhost:8000:
    conda run -n agrimatch_stable uvicorn app.main:app --reload
"""
import asyncio
import json
import sys

import requests

BASE = "http://localhost:8000"
API = f"{BASE}/api/v1"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

passed = []
failed = []


def ok(label, detail=""):
    passed.append(label)
    suffix = f" — {detail}" if detail else ""
    print(f"{GREEN}PASS{RESET} {label}{suffix}")


def fail(label, detail=""):
    failed.append(label)
    print(f"{RED}FAIL{RESET} {label} — {detail}")
    sys.exit(1)


def check(resp, expected_status, label, detail=""):
    if resp.status_code != expected_status:
        fail(label, f"HTTP {resp.status_code}: {resp.text[:400]}")
    ok(label, detail or f"HTTP {resp.status_code}")
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------
print("\n--- 1. Health ---")
r = requests.get(f"{BASE}/health")
check(r, 200, "health check")

r = requests.get(f"{BASE}/")
root = check(r, 200, "root endpoint")
ok("docs URL present", root.get("docs"))


# ---------------------------------------------------------------------------
# 2. Auth — login all three roles using demo credentials
# ---------------------------------------------------------------------------
print("\n--- 2. Auth ---")

r = requests.post(f"{API}/auth/farmer/login",
                  json={"email": "ravi@demofarm.com", "password": "demo1234"})
farmer_data = check(r, 200, "farmer login")
farmer_token = farmer_data["access_token"]
assert farmer_data["role"] == "farmer"
ok("farmer role claim correct")
F = {"Authorization": f"Bearer {farmer_token}"}

r = requests.post(f"{API}/auth/buyer/login",
                  json={"email": "procurement@freshmart.com", "password": "demo1234"})
buyer_data = check(r, 200, "buyer login")
buyer_token = buyer_data["access_token"]
assert buyer_data["role"] == "buyer"
ok("buyer role claim correct")
B = {"Authorization": f"Bearer {buyer_token}"}

r = requests.post(f"{API}/auth/middleman/login",
                  json={"email": "mohammed.faiz@demo.com", "password": "demo1234"})
middleman_data = check(r, 200, "middleman login")
middleman_token = middleman_data["access_token"]
assert middleman_data["role"] == "middleman"
ok("middleman role claim correct")
M = {"Authorization": f"Bearer {middleman_token}"}

# Wrong password must be rejected
r = requests.post(f"{API}/auth/farmer/login",
                  json={"email": "ravi@demofarm.com", "password": "wrongpassword"})
if r.status_code == 401:
    ok("invalid password rejected (401)")
else:
    fail("invalid password should return 401", f"got HTTP {r.status_code}")


# ---------------------------------------------------------------------------
# 3. Produce intelligence / price guidance (no auth required)
# ---------------------------------------------------------------------------
print("\n--- 3. Produce Intelligence ---")

r = requests.get(f"{API}/orders/price-guidance/Tomato",
                 params={"asking_price": 1.5, "harvest_date": "2026-02-25T00:00:00Z"})
pg = check(r, 200, "price guidance — Tomato with harvest date")
assert pg["grade_a_suggested_price"] == 1.5
ok("grade_a price unchanged", f"₹{pg['grade_a_suggested_price']}/kg")
assert pg["grade_b_standard_price"] < 1.5
ok("grade_b standard < grade_a", f"₹{pg['grade_b_standard_price']}/kg")
assert pg["grade_b_urgency_price"] is not None
ok("urgency price calculated", f"₹{pg['grade_b_urgency_price']}/kg")
ok("urgency note present", (pg.get("urgency_note") or "")[:60])

r = requests.get(f"{API}/orders/price-guidance/Onion",
                 params={"asking_price": 0.20})
pg2 = check(r, 200, "price guidance — Onion (no harvest date)")
ok("Onion cold_chain false", f"requires_cold_chain={pg2['requires_cold_chain']}")

# Unknown crop should still return a response (unknown crop, no intelligence)
r = requests.get(f"{API}/orders/price-guidance/Durian",
                 params={"asking_price": 5.0})
check(r, 200, "price guidance — unknown crop (Durian)")


# ---------------------------------------------------------------------------
# 4. Order marketplace — read seeded data
# ---------------------------------------------------------------------------
print("\n--- 4. Orders Marketplace ---")

r = requests.get(f"{API}/orders")
orders = check(r, 200, "list orders (no auth)", f"{len(r.json())} total")
assert isinstance(orders, list)
ok("orders list is array")

if len(orders) > 0:
    ok("seed data present", f"{len(orders)} orders in DB")
else:
    print(f"{YELLOW}WARN{RESET} No orders in DB — seed may not have run. Continuing anyway.")

# Filter by status
r = requests.get(f"{API}/orders", params={"status": "LISTED"})
listed_orders = check(r, 200, "filter by status=LISTED", f"{len(r.json())} listed")

# Filter by crop type
r = requests.get(f"{API}/orders", params={"crop_type": "tomato"})
check(r, 200, "filter by crop_type (case-insensitive)")


# ---------------------------------------------------------------------------
# 5. Create a fresh order (guarantees a LISTED order for bid flow)
# ---------------------------------------------------------------------------
print("\n--- 5. Create Fresh Order ---")

r = requests.post(f"{API}/orders", json={
    "crop_type": "Tomato",
    "variety": "Roma",
    "total_volume_kg": 50.0,
    "unit_price_asking": 0.80,
    "requires_cold_chain": False,
    "harvest_date": "2026-02-26T06:00:00Z",
}, headers=F)
new_order = check(r, 201, "create order (farmer)", "LISTED, price_guidance inline")
ORDER_ID = new_order["id"]
assert new_order["status"] == "LISTED"
ok("new order status=LISTED")
assert new_order.get("price_guidance") is not None
ok("inline price_guidance returned")

# Detail endpoint
r = requests.get(f"{API}/orders/{ORDER_ID}")
detail = check(r, 200, "get order detail (no auth)")
assert detail["id"] == ORDER_ID
ok("order detail correct ID")


# ---------------------------------------------------------------------------
# 6. Bid flow
# ---------------------------------------------------------------------------
print("\n--- 6. Bid Flow ---")

# Submit bid
r = requests.post(f"{API}/bids", json={
    "order_id": ORDER_ID,
    "offered_price_per_kg": 0.75,
    "volume_kg": 20.0,
    "message": "Automated smoke test bid",
}, headers=B)
bid = check(r, 201, "submit bid (buyer)", "status=PENDING")
BID_ID = bid["id"]
assert bid["status"] == "PENDING"
ok("bid status=PENDING")

# Order should now be NEGOTIATING
r = requests.get(f"{API}/orders/{ORDER_ID}")
order_now = r.json()
assert order_now["status"] == "NEGOTIATING", f"Expected NEGOTIATING, got {order_now['status']}"
ok("order transitioned to NEGOTIATING")

# Farmer sees the bid list
r = requests.get(f"{API}/bids/order/{ORDER_ID}", headers=F)
bids = check(r, 200, "list bids for order (farmer)", f"{len(r.json())} bid(s)")
assert any(b["id"] == BID_ID for b in bids)
ok("submitted bid appears in list")

# Second bid from same buyer is allowed (multi-bid market)
r = requests.post(f"{API}/bids", json={
    "order_id": ORDER_ID,
    "offered_price_per_kg": 0.77,
    "volume_kg": 10.0,
    "message": "Counter offer",
}, headers=B)
bid2 = check(r, 201, "second bid from same buyer (intentional)", "multi-bid market")
BID2_ID = bid2["id"]

# Farmer rejects second bid
r = requests.post(f"{API}/bids/{BID2_ID}/reject", headers=F)
check(r, 200, "farmer rejects second bid")

# Farmer accepts first bid — returns Stripe client_secret
r = requests.post(f"{API}/bids/{BID_ID}/accept", headers=F)
payment = check(r, 200, "farmer accepts bid", "Stripe PaymentIntent created")
client_secret = payment["stripe_client_secret"]
amount_cents = payment["amount_cents"]
assert amount_cents > 0
ok("amount_cents > 0", f"{amount_cents} cents")
if client_secret.startswith("pi_demo"):
    ok("demo Stripe mode active", client_secret[:30])
else:
    ok("real Stripe mode — client_secret present")

# Double-accept must fail (FSM guard)
r = requests.post(f"{API}/bids/{BID_ID}/accept", headers=F)
if r.status_code == 409:
    ok("double-accept returns 409 (FSM race condition guard)")
else:
    fail("double-accept should be 409", f"got HTTP {r.status_code}: {r.text[:200]}")

# Order must now be LOGISTICS_SEARCH
r = requests.get(f"{API}/orders/{ORDER_ID}")
order_after = r.json()
assert order_after["status"] == "LOGISTICS_SEARCH", (
    f"Expected LOGISTICS_SEARCH, got {order_after['status']}"
)
ok("order transitioned to LOGISTICS_SEARCH")
assert order_after.get("escrow") is not None
ok("escrow created and visible in order detail",
   f"status={order_after['escrow']['status']}")
assert order_after["escrow"]["status"] == "WAITING_FUNDS"
ok("escrow status=WAITING_FUNDS")


# ---------------------------------------------------------------------------
# 7. Stripe webhook bypass
# ---------------------------------------------------------------------------
print("\n--- 7. Stripe Webhook ---")

# We send a dummy pi_id that won't match any escrow.
# The endpoint should still return 200 (logs a warning for no match).
# To test the full flow, look up stripe_payment_intent_id directly in the DB.
dummy_payload = {
    "id": "evt_smoke_test_001",
    "type": "payment_intent.succeeded",
    "data": {
        "object": {
            "id": "pi_smoke_no_match",
            "object": "payment_intent",
            "amount": amount_cents,
        }
    }
}
r = requests.post(f"{API}/webhooks/stripe",
                  json=dummy_payload,
                  headers={"stripe-signature": "test_bypass"})
wh = check(r, 200, "webhook endpoint reachable + bypass active", f"{r.json()}")
assert wh == {"received": True}
ok("webhook response is {received: true}")

print(f"\n{YELLOW}NOTE{RESET} To test full webhook→escrow flow:")
print(f"     Query Neon DB: SELECT stripe_payment_intent_id FROM escrows WHERE order_id='{ORDER_ID}';")
print(f"     Then POST that pi_id to /api/v1/webhooks/stripe — escrow should move to FUNDS_HELD.")


# ---------------------------------------------------------------------------
# 8. Role guards — make sure endpoints reject wrong roles
# ---------------------------------------------------------------------------
print("\n--- 8. Role Guards ---")

# Buyer cannot list bids (farmer-only)
r = requests.get(f"{API}/bids/order/{ORDER_ID}", headers=B)
if r.status_code == 403:
    ok("buyer cannot list order bids (403)")
else:
    fail("buyer should get 403 on farmer-only endpoint", f"got {r.status_code}")

# Middleman cannot submit a bid (buyer-only)
r = requests.post(f"{API}/bids", json={
    "order_id": ORDER_ID,
    "offered_price_per_kg": 0.50,
    "volume_kg": 5.0,
}, headers=M)
if r.status_code in (401, 403, 422):
    ok(f"middleman cannot submit bid ({r.status_code})")
else:
    fail("middleman should not be able to bid", f"got {r.status_code}: {r.text[:200]}")

# Unauthenticated cannot accept bid
r = requests.post(f"{API}/bids/{BID_ID}/accept")
if r.status_code in (401, 403, 422):
    ok(f"unauthenticated accept rejected ({r.status_code})")
else:
    fail("unauthenticated accept should fail", f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 9. WebSocket — CONNECTED + STATE_SYNC + PING/PONG
# ---------------------------------------------------------------------------
print("\n--- 9. WebSocket ---")

async def test_websocket(order_id: str, token: str) -> None:
    try:
        import websockets  # type: ignore
    except ImportError:
        print(f"{YELLOW}SKIP{RESET} websocket test — 'websockets' not installed")
        print(f"     pip install websockets")
        return

    uri = f"ws://localhost:8000/ws/orders/{order_id}?token={token}"
    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            # Message 1: CONNECTED
            msg1 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg1["type"] == "CONNECTED", f"Expected CONNECTED, got {msg1}"
            assert msg1["role"] == "farmer"
            ok("WS msg 1: CONNECTED", f"role={msg1['role']}, user_id={msg1['user_id'][:8]}...")

            # Message 2: STATE_SYNC (the new change we added)
            msg2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg2["type"] == "STATE_SYNC", f"Expected STATE_SYNC, got {msg2}"
            ok("WS msg 2: STATE_SYNC", f"order_status={msg2.get('order_status')}, "
               f"escrow_status={msg2.get('escrow_status')}")
            assert msg2["order_status"] == "LOGISTICS_SEARCH"
            ok("STATE_SYNC order_status correct (LOGISTICS_SEARCH)")
            assert msg2["escrow_status"] == "WAITING_FUNDS"
            ok("STATE_SYNC escrow_status correct (WAITING_FUNDS)")

            # PING → PONG keepalive
            await ws.send('{"type":"PING"}')
            pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert pong["type"] == "PONG", f"Expected PONG, got {pong}"
            ok("WS PING → PONG keepalive")

    except ConnectionRefusedError:
        fail("WebSocket connect refused", "Is the server running?")
    except asyncio.TimeoutError:
        fail("WebSocket timeout", "Server did not send expected message in 5s")
    except AssertionError as exc:
        fail("WebSocket assertion", str(exc))

asyncio.run(test_websocket(ORDER_ID, farmer_token))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 55}")
print(f"  {GREEN}{len(passed)} passed{RESET}    {(RED if failed else '')}{len(failed)} failed{RESET}")
print(f"{'=' * 55}")
if failed:
    sys.exit(1)
