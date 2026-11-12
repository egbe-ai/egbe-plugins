"""Capture/finalize state transitions and bounded, explicitly resumed delivery."""
import time
from uuid import uuid4

from . import protocol, transport


def capture(store, paths, *, unknown=False):
    selected = protocol.method_paths(store.root, paths)
    for record in store.records():
        if record["status"] == "captured" and set(paths) & {item["path"] for item in record["files"]}:
            raise ValueError("An unfinished capture already includes this file; resume or explicitly discard it")
    base, key = transport.connection(store.root)
    project_id = transport.identity(base, key)
    files = [{"path": name, "before": protocol.snapshot(store.root, name, before=True, unknown=unknown)}
             for name, _ in selected]
    value = {"version": 1, "change_id": str(uuid4()), "origin": base,
             "expected_project_id": project_id, "files": files, "status": "captured",
             "created_at": protocol.now(), "attempts": 0, "next_retry_at": 0}
    if len(protocol.canonical(files)) > protocol.MAX_PACKET:
        raise ValueError("Selected before snapshots exceed the 2 MiB packet budget")
    store.save(value, new=True)
    return {"change_id": value["change_id"], "status": value["status"], "files": len(files)}


def finalize(store, identity, *, reason, expected_effect, initiator):
    value = store.load(identity)
    if value["status"] != "captured":
        raise ValueError("This capture is already finalized; send its existing packet")
    reason = protocol.metadata(reason, "reason", 4000)
    effect = protocol.metadata(expected_effect, "expected_effect", 4000)
    initiator = protocol.metadata(initiator, "initiator", 256)
    paths = protocol.method_paths(store.root, [item["path"] for item in value["files"]])
    changed = []
    for item, (name, _) in zip(value["files"], paths):
        before, after = item["before"], protocol.snapshot(store.root, name)
        same = before["state"] == after["state"] and before["text"] == after["text"]
        same = same or before["state"] == "absent" and after["state"] == "deleted"
        if not same:
            changed.append({**item, "after": after})
    if not changed:
        # Retain a compact local disposition; no server event and no private text.
        value.pop("files")
        value["status"] = "no_change"
        store.save(value)
        return {"change_id": identity, "status": "no_change"}
    packet = {"client_change_id": identity, "expected_project_id": value["expected_project_id"],
              "reason": reason, "expected_effect": effect, "initiator": initiator, "files": changed}
    if len(protocol.canonical(packet)) > protocol.MAX_PACKET:
        raise ValueError("Change packet exceeds 2 MiB; capture is preserved, do not truncate the text")
    value.pop("files")
    value.update(status="pending", packet=packet, content_hash=protocol.digest(packet))
    store.save(value)
    return {"change_id": identity, "status": "pending", "files": len(changed)}


def failure(store, value, error):
    value["attempts"] += 1
    value["error_code"] = error.code
    if error.transient:
        value["status"] = "pending"
        value["next_retry_at"] = time.time() + max(error.retry_after, min(60 * 2 ** min(value["attempts"] - 1, 10), 3600))
    else:
        value["status"] = "held"
        value["next_retry_at"] = 0
    store.save(value)


def send(store, *, retry_held=None, max_packets=5, budget_seconds=30):
    if not 1 <= max_packets <= 5 or not 1 <= budget_seconds <= 30:
        raise ValueError("Send is limited to five packets and thirty seconds")
    if retry_held:
        protocol.change_id(retry_held)
        target = store.load(retry_held)
        if target["status"] != "held":
            raise ValueError("Explicit retry expects a held record")
    # An explicit recovery request must not be starved by unrelated due packets.
    records = [target] if retry_held else [value for value in store.records() if
               value["status"] == "pending" and value["next_retry_at"] <= time.time()]
    records = records[:max_packets]
    if not records:
        return {"attempted": 0, "delivered": 0, "pending": 0, "held": 0}
    base, key = transport.connection(store.root)
    deadline = time.monotonic() + budget_seconds
    result = {"attempted": 0, "delivered": 0, "pending": 0, "held": 0}
    project = None
    identity_error = None
    for value in records:
        if time.monotonic() >= deadline:
            break
        result["attempted"] += 1
        try:
            if value["origin"] != base:
                raise transport.DeliveryError("origin_mismatch")
            if (protocol.digest(value["packet"]) != value["content_hash"]
                    or value["packet"].get("client_change_id") != value["change_id"]
                    or value["packet"].get("expected_project_id") != value["expected_project_id"]):
                raise transport.DeliveryError("frozen_packet_changed")
            if identity_error:
                raise identity_error
            if project is None:
                try:
                    project = transport.identity(base, key, timeout=max(0.1, min(10, deadline - time.monotonic())))
                except transport.DeliveryError as error:
                    identity_error = error
                    raise
            if project != value["expected_project_id"]:
                raise transport.DeliveryError("project_mismatch")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise transport.DeliveryError("delivery_budget_exhausted", transient=True)
            received = transport.request(base, key, "/playbooks/changes", packet=value["packet"], timeout=min(10, remaining))
            try:
                receipt = protocol.receipt(received, value["content_hash"])
            except (ValueError, TypeError, AttributeError):
                raise transport.DeliveryError("unverified_receipt", transient=True) from None
            value.update(status="delivered", receipt=receipt, next_retry_at=0)
            value.pop("error_code", None)
            # The server confirmed the immutable packet: keep only the receipt
            # locally, not an unbounded second archive of method snapshots.
            value.pop("packet")
            store.save(value)
        except transport.DeliveryError as error:
            failure(store, value, error)
        result[value["status"]] += 1
    return result


def status(store, identity=None):
    values = [store.load(identity)] if identity else [value for value in store.records()
                                                    if value["status"] in {"captured", "pending", "held"}]
    return [{"change_id": value["change_id"], "status": value["status"],
             "project_id": value["expected_project_id"], "created_at": value["created_at"],
             **({"error_code": value["error_code"]} if value.get("error_code") else {}),
             **({"next_retry_at": value["next_retry_at"]} if value.get("next_retry_at") else {}),
             **({"receipt": value["receipt"]} if value.get("receipt") else {})}
            for value in values]
