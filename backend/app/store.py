"""Best-effort DynamoDB persistence shared by the passport + the demo stores.

Single-table design over the existing SecondLifePassport table (PK item_id:S,
SK ts:S). Synthetic partition keys namespace the non-passport stores so one table
+ one IAM policy cover everything:

    passport events : pk=<item_id>        sk=<event ts, microsecond>
    resell listings : pk="LISTING"        sk=<listing_id>
    returns desk    : pk="RETURNS"        sk=<return_id>
    buyer carts     : pk="CART#<persona>" sk="cart"

THE IRON RULE: a DynamoDB problem (no table, no creds, throttle, timeout) must
NEVER block the demo. When DYNAMODB_TABLE_NAME is unset we don't touch boto3 at
all — every call no-ops and the caller uses its in-memory store, exactly as before.
When it IS set, every call is wrapped: writes are fire-and-forget, reads return
[] / None on any error so the caller falls back to memory. Short timeouts keep a
slow table from eating the Lambda budget.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("store")

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "")

_table = None


def enabled() -> bool:
    return bool(TABLE_NAME)


def _table_handle():
    """Lazily build a short-timeout DynamoDB table handle, or None if disabled.
    Never raises — a client-construction failure degrades to in-memory."""
    global _table
    if not TABLE_NAME:
        return None
    if _table is None:
        try:
            import boto3
            from botocore.config import Config
            cfg = Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1})
            _table = boto3.resource("dynamodb", config=cfg).Table(TABLE_NAME)
        except Exception as e:  # pragma: no cover - exercised only on misconfig
            log.warning("DynamoDB client init failed (%s) — using in-memory only.", e)
            return None
    return _table


def put(pk: str, sk: str, data: dict) -> None:
    """Write one row (overwrites the same pk+sk). Fire-and-forget."""
    t = _table_handle()
    if t is None:
        return
    try:
        t.put_item(Item={"item_id": pk, "ts": sk, "data": json.dumps(data)}) 
        #json.dumps() converts python dict to string so that it can be stored in dynamodb
    except Exception as e:
        log.warning("DynamoDB put failed (%s/%s): %s — in-memory store still holds it.", pk, sk, e)


def query(pk: str) -> list[dict]:
    """All rows under a partition, as {"sk", "data"} dicts. [] on any failure."""
    t = _table_handle()
    if t is None:
        return []
    try:
        from boto3.dynamodb.conditions import Key
        out: list[dict] = []
        resp = t.query(KeyConditionExpression=Key("item_id").eq(pk))
        items = list(resp.get("Items", []))
        # paginate (demo volumes are tiny, but be correct)
        while "LastEvaluatedKey" in resp:
            resp = t.query(KeyConditionExpression=Key("item_id").eq(pk),
                           ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        for it in items:
            raw = it.get("data")
            out.append({"sk": it.get("ts"), "data": json.loads(raw) if raw else {}})
        return out
    except Exception as e:
        log.warning("DynamoDB query failed (%s): %s — falling back to in-memory.", pk, e)
        return []


def get(pk: str, sk: str) -> dict | None:
    """One row's data blob, or None if absent / on any failure."""
    t = _table_handle()
    if t is None:
        return None
    try:
        resp = t.get_item(Key={"item_id": pk, "ts": sk})
        it = resp.get("Item")
        if not it:
            return None
        raw = it.get("data")
        return json.loads(raw) if raw else {} #convert back to python dict
    except Exception as e:
        log.warning("DynamoDB get failed (%s/%s): %s — falling back to in-memory.", pk, sk, e)
        return None
