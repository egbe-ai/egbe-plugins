#!/usr/bin/env python3
"""Start, resume, poll, and persist one bounded OS/Apify dataset run."""

from __future__ import annotations

import runpy as _egbe_runpy
from pathlib import Path as _EgbePath
_egbe_adapter = _EgbePath(__file__).with_name("connection_identity.py")
_connection_headers = _egbe_runpy.run_path(str(_egbe_adapter))["connection_headers"] if _egbe_adapter.is_file() else lambda _url: {}

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from _analysis import _validate_normalized
from _contract import (
    CANONICAL_PROVIDER_RUNS,
    ContractError,
    PROVIDER_INPUT_CONTRACT_VERSION,
    SCHEMA_VERSION,
    TIKTOK_COMMENTS_BUNDLE_PATH,
    TIKTOK_COMMENTS_LINK_KIND,
    atomic_write_json,
    linked_tiktok_comment_requests,
    load_run_state,
    provider_idempotency_key,
    provider_run_lock,
    read_json,
    resolve_relative,
    save_run_state,
    sha256_file,
    utc_now,
    validate_accounts_file,
    validate_context,
    validate_manifest_against_state,
    validate_raw_manifest,
    validate_linked_tiktok_comments_bundle,
)
from _provider_inputs import (build_discovery_inputs, build_enrichment_inputs,
                              collection_window, validate_collection_window,
                              validate_provider_input)


ACTIVE = {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}
FAILED = {"FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


def _data(value: dict[str, Any]) -> dict[str, Any]:
    data = value.get("data")
    return data if isinstance(data, dict) else value


def _request(
    *,
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    request_json: str | None = None,
    idempotency_key: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    payload: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = (request_json if request_json is not None else
                   json.dumps(body, separators=(",", ":"))).encode("utf-8")
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        for _name, _value in _connection_headers(request.full_url).items():
            request.add_unredirected_header(_name, _value)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(64 * 1024).decode("utf-8", errors="replace")
        try:
            value = json.loads(detail)
        except json.JSONDecodeError:
            value = None
        data = value.get("data") if isinstance(value, dict) else None
        run_id = data.get("run_id") if isinstance(data, dict) else None
        if (
            500 <= exc.code < 600 and method == "POST"
            and urllib.parse.urlparse(url).path == "/scrape/apify/run"
            and body is not None and body.get("sync") is False
            and isinstance(data, dict) and data.get("source") == "apify"
            and data.get("resubmit_allowed") is False
            and isinstance(run_id, str) and 1 <= len(run_id) <= 128
            and run_id.isascii() and all(c.isalnum() or c in "_-" for c in run_id)
        ):
            # The paid run exists. Let main persist its receipt before polling
            # or reporting reconciliation, so another invocation cannot POST.
            return value
        raise ContractError(f"OS returned HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise ContractError(f"OS request failed: {exc.reason}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("OS returned a non-JSON response") from exc
    if isinstance(value, list):
        return {"data": {"rows": value}}
    if not isinstance(value, dict):
        raise ContractError("OS response must be an object")
    return value


def _handle(value: dict[str, Any]) -> tuple[str, str, str]:
    data = _data(value)
    run_id = str(data.get("run_id") or data.get("id") or "").strip()
    dataset_id = str(
        data.get("dataset_id") or data.get("defaultDatasetId") or ""
    ).strip()
    status = str(data.get("status") or "").strip().upper()
    return run_id, dataset_id, status


def _enrichment_selection(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Reuse a validated discovery sample while other enrichment adds raw data."""
    manifest = validate_raw_manifest(root)
    validate_manifest_against_state(root, manifest, state)
    proof = {
        "normalized_sha256": sha256_file(root / "normalized/videos.json"),
        "selection_sha256": sha256_file(root / "normalized/selection.json"),
    }
    prior = state.get("enrichment_selection")
    if prior is not None and not isinstance(prior, dict):
        raise ContractError("saved enrichment selection proof is invalid")
    if prior is not None and prior.get("selection_sha256") != proof["selection_sha256"]:
        raise ContractError("frozen enrichment selection changed")
    if prior == proof:
        # The first enrichment may have updated the full manifest. The exact
        # already-validated sample remains usable only for the same discoveries.
        selection = read_json(root / "normalized/selection.json")
        discovery_sources = sorted(
            [{"path": item["path"], "sha256": item["sha256"]}
             for item in manifest["datasets"] if item["kind"] == "discovery"],
            key=lambda item: item["path"],
        )
        if (selection.get("collection_epoch") != state["collection_epoch"]
                or selection.get("collection_window") != state["collection_window"]
                or selection.get("discovery_sources") != discovery_sources):
            raise ContractError("frozen enrichment discovery evidence changed")
        normalized = read_json(root / "normalized/videos.json")
    else:
        normalized, _ = _validate_normalized(root)
        state["enrichment_selection"] = proof
    return normalized


def _ensure_tiktok_comments_bundle(
    root: Path,
    *,
    main_output: Path,
    os_url: str,
    token: str,
    dataset_limit: int,
    reread_dataset_id: str | None = None,
) -> None:
    """Persist every linked comments dataset exposed by TikTok enrichment.

    The actor shares one comments dataset across all videos of a run, so the
    read uses the run's dataset limit, not the per-video comment count.
    The gateway grants a comments dataset while it serves the run's video
    rows. A retry from saved output passes `reread_dataset_id` so that grant
    is attempted again; the reread rows are discarded.
    """

    main_payload = read_json(main_output)
    requests = linked_tiktok_comment_requests(main_payload)
    bundle_path = root / TIKTOK_COMMENTS_BUNDLE_PATH
    if bundle_path.is_file():
        validate_linked_tiktok_comments_bundle(main_payload, read_json(bundle_path))
        return

    if requests and reread_dataset_id:
        query = urllib.parse.urlencode({"limit": dataset_limit})
        _request(
            method="GET",
            url=(
                f"{os_url}/scrape/apify/datasets/"
                f"{urllib.parse.quote(reread_dataset_id, safe='')}?{query}"
            ),
            token=token,
        )
    datasets: list[dict[str, Any]] = []
    for request in requests:
        dataset_id = request["dataset_id"]
        query = urllib.parse.urlencode({"limit": dataset_limit})
        response = _request(
            method="GET",
            url=(
                f"{os_url}/scrape/apify/datasets/"
                f"{urllib.parse.quote(dataset_id, safe='')}?{query}"
            ),
            token=token,
        )
        datasets.append({**request, "response": response})
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "source_logical_key": "tiktok-enrichment",
        "source_dataset_sha256": sha256_file(main_output),
        "datasets": datasets,
    }
    validate_linked_tiktok_comments_bundle(main_payload, bundle)
    atomic_write_json(bundle_path, bundle)


def _write_manifest(
    root: Path,
    *,
    accounts: list[dict[str, Any]],
    platform: str,
    kind: str,
    raw_path: str,
    state: dict[str, Any],
    collection_changed: bool,
) -> None:
    path = root / "raw/manifest.json"
    if path.exists():
        manifest = read_json(path)
        started_at = manifest.get("collection_started_at") or state["collection_window"]["reference_at"]
        datasets = manifest.get("datasets")
        if not isinstance(datasets, list):
            datasets = []
    else:
        started_at = state["collection_window"]["reference_at"]
        datasets = []
        manifest = {}
    dataset = {
        "platform": platform,
        "kind": kind,
        "path": raw_path,
        "sha256": sha256_file(resolve_relative(root, raw_path, "raw output")),
    }
    datasets = [
        item
        for item in datasets
        if not (
            isinstance(item, dict)
            and item.get("platform") == platform
            and item.get("kind") == kind
        )
    ]
    datasets.append(dataset)
    datasets.sort(key=lambda item: (item["platform"], item["kind"], item["path"]))

    runs: list[dict[str, Any]] = []
    for key in sorted(state["provider_runs"]):
        run = state["provider_runs"][key]
        raw_path = run.get("raw_path")
        if (
            run.get("status") != "SUCCEEDED"
            or not isinstance(raw_path, str)
            or not resolve_relative(root, raw_path, "provider raw path").is_file()
        ):
            continue
        runs.append(
            {
                "logical_key": key,
                "provider": "apify",
                "actor_id": run["actor_id"],
                "run_id": run["run_id"],
                "dataset_id": run["dataset_id"],
                "status": "SUCCEEDED",
                "input_sha256": run["input_sha256"],
                "input_contract_version": run["input_contract_version"],
                "input_keys": run["input_keys"],
                "actor_metadata": run["actor_metadata"],
            }
        )
    completed_at = (
        utc_now()
        if collection_changed
        else manifest.get("collection_completed_at")
        or max(
            (
                str(run.get("completed_at") or "")
                for run in state["provider_runs"].values()
                if isinstance(run, dict) and run.get("status") == "SUCCEEDED"
            ),
            default="",
        )
    )
    if not completed_at:
        raise ContractError("cannot determine collection completion time")
    linked_comments_path = root / TIKTOK_COMMENTS_BUNDLE_PATH
    linked_datasets = (
        [
            {
                "kind": TIKTOK_COMMENTS_LINK_KIND,
                "parent_logical_key": "tiktok-enrichment",
                "path": TIKTOK_COMMENTS_BUNDLE_PATH,
                "sha256": sha256_file(linked_comments_path),
            }
        ]
        if linked_comments_path.is_file()
        else []
    )
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "collection_epoch": state["collection_epoch"],
            "collection_started_at": started_at,
            "collection_completed_at": completed_at,
            "accounts": accounts,
            "accounts_source": state["accounts_source"],
            "datasets": datasets,
            "linked_datasets": linked_datasets,
            "provider_runs": runs,
        },
    )


def _save_provider(
    root: Path,
    state: dict[str, Any],
    *,
    key: str,
    actor_id: str,
    input_hash: str,
    input_path: str,
    input_keys: list[str],
    actor_metadata: dict[str, str],
    idempotency_key: str,
    run_id: str,
    dataset_id: str,
    status: str,
    raw_path: str | None = None,
) -> None:
    existing = state["provider_runs"].get(key)
    if isinstance(existing, dict):
        for field, expected in (
            ("actor_id", actor_id),
            ("input_sha256", input_hash),
            ("input_path", input_path),
            ("input_contract_version", PROVIDER_INPUT_CONTRACT_VERSION),
            ("input_keys", input_keys),
            ("actor_metadata", actor_metadata),
        ):
            if existing.get(field) != expected:
                raise ContractError(f"logical provider run {key} changed {field}")
        if existing.get("run_id") and existing["run_id"] != run_id:
            raise ContractError(f"logical provider run {key} changed run_id")
        if existing.get("dataset_id") and dataset_id and existing["dataset_id"] != dataset_id:
            raise ContractError(f"logical provider run {key} changed dataset_id")
    value = {
        "provider": "apify",
        "actor_id": actor_id,
        "input_sha256": input_hash,
        "input_path": input_path,
        "input_contract_version": PROVIDER_INPUT_CONTRACT_VERSION,
        "input_keys": input_keys,
        "actor_metadata": actor_metadata,
        "idempotency_key": idempotency_key,
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": status,
        "started_at": (existing or {}).get("started_at") or utc_now(),
        "updated_at": utc_now(),
    }
    for field in ("attempted_at", "request_json"):
        if isinstance(existing, dict) and field in existing:
            value[field] = existing[field]
    if raw_path:
        value["raw_path"] = raw_path
        value["raw_sha256"] = sha256_file(resolve_relative(root, raw_path, "raw output"))
    if status == "SUCCEEDED":
        value["completed_at"] = (existing or {}).get("completed_at") or utc_now()
    state["provider_runs"][key] = value
    save_run_state(root, state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--platform", choices=("tiktok", "instagram"), required=True)
    parser.add_argument("--kind", choices=("discovery", "enrichment"), required=True)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--accounts-file", type=Path, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-limit", type=int, default=1000)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--poll-timeout-seconds", type=int, default=1200)
    parser.add_argument("--start-only", action="store_true")
    args = parser.parse_args()

    root = args.runtime_root.resolve()
    try:
        with provider_run_lock(root):
            return _run(args, root)
    except (ContractError, OSError) as exc:
        print(f"organic trend Apify run failed: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace, root: Path) -> int:
    try:
        if not 1 <= args.dataset_limit <= 5000:
            raise ContractError("dataset limit must be between 1 and 5000")
        if not 5 <= args.poll_interval_seconds <= 60:
            raise ContractError("poll interval must be between 5 and 60 seconds")
        if not 1 <= args.poll_timeout_seconds <= 3600:
            raise ContractError("poll timeout must be between 1 and 3600 seconds")
        os_url = os.environ.get("OS_URL", "").rstrip("/")
        token = os.environ.get("OS_API_KEY", "")
        if not os_url or not token:
            raise ContractError("OS_URL and OS_API_KEY are required")
        canonical_run = CANONICAL_PROVIDER_RUNS.get(args.key)
        if canonical_run is None:
            raise ContractError("key must name one of the four canonical provider runs")
        if (
            args.actor_id != canonical_run["actor_id"]
            or args.platform != canonical_run["platform"]
            or args.kind != canonical_run["kind"]
        ):
            raise ContractError("key, actor, platform, and kind do not match the canonical run")
        actor_input_path = args.input_file.resolve()
        expected_input_path = (root / f"raw/{args.key}-input.json").resolve()
        if actor_input_path != expected_input_path:
            raise ContractError(
                f"input-file must be the canonical raw/{args.key}-input.json adapter output"
            )
        actor_input = read_json(actor_input_path)
        validate_provider_input(args.key, actor_input)
        input_keys = sorted(actor_input)
        expected_accounts_path = (root / "raw/accounts.json").resolve()
        if args.accounts_file.resolve() != expected_accounts_path:
            raise ContractError("accounts-file must be raw/accounts.json")
        accounts, accounts_source = validate_accounts_file(root)
        output_path = resolve_relative(root, args.output, "output")
        if args.output != f"raw/{args.key}.json" or output_path.parent != (root / "raw").resolve():
            raise ContractError(f"output must be raw/{args.key}.json")

        state = load_run_state(root)
        context = validate_context(root / "context.json")
        # Calendar validation only; do not persist a preview as a first attempt.
        collection_window(context, utc_now())
        window = state.get("collection_window")
        if window is not None:
            validate_collection_window(context, window)
        elif state["provider_runs"]:
            raise ContractError("saved provider state has no frozen collection window; do not resubmit")
        existing = state["provider_runs"].get(args.key)
        if existing is not None and not isinstance(existing, dict):
            raise ContractError("saved provider run is invalid; do not resubmit")
        if args.kind == "discovery":
            expected = build_discovery_inputs(accounts, context, window).get(args.key)
            preview = build_discovery_inputs(accounts, context).get(args.key)
            if actor_input not in (expected, preview):
                raise ContractError("discovery input differs from context and declared accounts")
        elif existing is None:
            normalized = _enrichment_selection(root, state)
            if actor_input != build_enrichment_inputs(normalized["videos"]).get(args.key):
                raise ContractError("enrichment input differs from the frozen selection")
        if state.get("accounts_source") is None:
            state["accounts_source"] = accounts_source
            save_run_state(root, state)
        elif state.get("accounts_source") != accounts_source:
            raise ContractError("raw/accounts.json changed within this collection epoch")
        input_hash = sha256_file(actor_input_path)
        input_relative = actor_input_path.relative_to(root).as_posix()
        idempotency_key = provider_idempotency_key(
            state["context_sha256"],
            state["collection_epoch"],
            args.key,
            args.actor_id,
            input_hash,
        )
        if isinstance(existing, dict):
            expected_existing = {
                "actor_id": args.actor_id,
                "input_sha256": input_hash,
                "input_path": input_relative,
                "input_contract_version": PROVIDER_INPUT_CONTRACT_VERSION,
                "input_keys": input_keys,
            }
            for field, expected in expected_existing.items():
                if existing.get(field) != expected:
                    raise ContractError(
                        f"logical provider run {args.key} has different {field}"
                    )
            actor_metadata = existing.get("actor_metadata")
            if not isinstance(actor_metadata, dict):
                raise ContractError("saved provider run has no actor metadata snapshot")
            metadata_path = resolve_relative(
                root, actor_metadata.get("path"), "actor metadata path"
            )
            if (
                not metadata_path.is_file()
                or actor_metadata.get("sha256") != sha256_file(metadata_path)
            ):
                raise ContractError("saved actor metadata snapshot hash changed")
            run_id = str(existing.get("run_id") or "")
            dataset_id = str(existing.get("dataset_id") or "")
            status = str(existing.get("status") or "").upper()
            if existing.get("idempotency_key") != idempotency_key:
                raise ContractError("saved provider idempotency key changed")
            if args.start_only and run_id:
                if status in FAILED:
                    raise ContractError(f"Apify run {run_id} is terminal: {status}")
                print(json.dumps(existing, sort_keys=True))
                return 0
            if (
                status == "SUCCEEDED"
                and output_path.is_file()
                and existing.get("raw_sha256")
            ):
                if existing.get("raw_sha256") != sha256_file(output_path):
                    raise ContractError("saved raw dataset hash changed")
                if args.key == "tiktok-enrichment":
                    _ensure_tiktok_comments_bundle(
                        root,
                        main_output=output_path,
                        os_url=os_url,
                        token=token,
                        dataset_limit=args.dataset_limit,
                        reread_dataset_id=dataset_id,
                    )
                _write_manifest(
                    root,
                    accounts=accounts,
                    platform=args.platform,
                    kind=args.kind,
                    raw_path=args.output,
                    state=state,
                    collection_changed=False,
                )
                print(f"reused {args.key} run {run_id}")
                return 0
        else:
            metadata_path = root / f"raw/{args.key}-actor-metadata.json"
            metadata_response = _request(
                method="GET",
                url=(
                    f"{os_url}/scrape/apify/actors/"
                    f"{urllib.parse.quote(args.actor_id, safe='/~')}"
                ),
                token=token,
            )
            if _data(metadata_response).get("actor_id") != args.actor_id:
                raise ContractError("OS actor metadata response changed actor_id")
            atomic_write_json(metadata_path, metadata_response)
            actor_metadata = {
                "path": metadata_path.relative_to(root).as_posix(),
                "sha256": sha256_file(metadata_path),
            }
            # Preview/init dates are not a paid attempt. Freeze the effective
            # input and reference time immediately before the first POST.
            attempted_at = utc_now()
            if window is None:
                window = collection_window(context, attempted_at)
                state["collection_window"] = window
            if args.kind == "discovery":
                actor_input = build_discovery_inputs(accounts, context, window)[args.key]
                atomic_write_json(actor_input_path, actor_input)
                input_hash = sha256_file(actor_input_path)
                idempotency_key = provider_idempotency_key(
                    state["context_sha256"], state["collection_epoch"],
                    args.key, args.actor_id, input_hash,
                )
            state["provider_runs"][args.key] = {
                "provider": "apify", "actor_id": args.actor_id,
                "input_sha256": input_hash, "input_path": input_relative,
                "input_contract_version": PROVIDER_INPUT_CONTRACT_VERSION,
                "input_keys": input_keys, "actor_metadata": actor_metadata,
                "idempotency_key": idempotency_key,
                "run_id": "", "dataset_id": "", "status": "SUBMITTING",
                "started_at": attempted_at, "attempted_at": attempted_at,
                "request_json": json.dumps(
                    {"actor": args.actor_id, "input": actor_input, "sync": False},
                    separators=(",", ":"),
                ),
            }
            save_run_state(root, state)
            run_id, dataset_id, status = "", "", "SUBMITTING"

        if not run_id:
            saved = state["provider_runs"][args.key]
            request_json = saved.get("request_json")
            expected_body = {"actor": args.actor_id, "input": actor_input, "sync": False}
            try:
                saved_body = json.loads(request_json) if isinstance(request_json, str) else None
            except json.JSONDecodeError as exc:
                raise ContractError("saved provider request is invalid; do not resubmit") from exc
            if (not isinstance(request_json, str) or not saved.get("attempted_at")
                    or saved_body != expected_body):
                raise ContractError("uncertain submission lacks its exact saved request; do not resubmit")
            # The gateway durably reconciles this same key/body. Never mint a
            # replacement operation when a response or handle is missing.
            response = _request(
                method="POST",
                url=f"{os_url}/scrape/apify/run",
                token=token,
                body=expected_body,
                request_json=request_json,
                idempotency_key=idempotency_key,
            )
            run_id, dataset_id, status = _handle(response)
            if not run_id:
                raise ContractError("OS start response did not include run_id")
            _save_provider(
                root,
                state,
                key=args.key,
                actor_id=args.actor_id,
                input_hash=input_hash,
                input_path=input_relative,
                input_keys=input_keys,
                actor_metadata=actor_metadata,
                idempotency_key=idempotency_key,
                run_id=run_id,
                dataset_id=dataset_id,
                status=status or "READY",
            )
            state = load_run_state(root)
            if _data(response).get("reconciliation_required") is True:
                raise ContractError(f"Apify run {run_id} started and its handle was saved; Egbe team reconciliation is required. Do not submit another run.")
            if args.start_only:
                print(json.dumps(state["provider_runs"][args.key], sort_keys=True))
                return 0

        if status in FAILED:
            raise ContractError(f"Apify run {run_id} is terminal: {status}")
        deadline = time.monotonic() + args.poll_timeout_seconds
        while status != "SUCCEEDED":
            if status and status not in ACTIVE:
                raise ContractError(f"Apify run {run_id} has unsupported status: {status}")
            if time.monotonic() >= deadline:
                print(f"Apify run {run_id} is still {status}; retry will resume it", file=sys.stderr)
                return 2
            time.sleep(args.poll_interval_seconds)
            response = _request(
                method="GET",
                url=f"{os_url}/scrape/apify/runs/{urllib.parse.quote(run_id, safe='')}",
                token=token,
            )
            polled_run_id, polled_dataset_id, status = _handle(response)
            if polled_run_id and polled_run_id != run_id:
                raise ContractError("OS poll response changed run_id")
            dataset_id = polled_dataset_id or dataset_id
            _save_provider(
                root,
                state,
                key=args.key,
                actor_id=args.actor_id,
                input_hash=input_hash,
                input_path=input_relative,
                input_keys=input_keys,
                actor_metadata=actor_metadata,
                idempotency_key=idempotency_key,
                run_id=run_id,
                dataset_id=dataset_id,
                status=status,
            )
            state = load_run_state(root)
            if status in FAILED:
                raise ContractError(f"Apify run {run_id} failed: {status}")

        if not dataset_id:
            raise ContractError(f"successful Apify run {run_id} has no dataset_id")
        query = urllib.parse.urlencode({"limit": args.dataset_limit})
        response = _request(
            method="GET",
            url=f"{os_url}/scrape/apify/datasets/{urllib.parse.quote(dataset_id, safe='')}?{query}",
            token=token,
        )
        atomic_write_json(output_path, response)
        _save_provider(
            root,
            state,
            key=args.key,
            actor_id=args.actor_id,
            input_hash=input_hash,
            input_path=input_relative,
            input_keys=input_keys,
            actor_metadata=actor_metadata,
            idempotency_key=idempotency_key,
            run_id=run_id,
            dataset_id=dataset_id,
            status="SUCCEEDED",
            raw_path=args.output,
        )
        state = load_run_state(root)
        if args.key == "tiktok-enrichment":
            _ensure_tiktok_comments_bundle(
                root,
                main_output=output_path,
                os_url=os_url,
                token=token,
                dataset_limit=args.dataset_limit,
            )
        _write_manifest(
            root,
            accounts=accounts,
            platform=args.platform,
            kind=args.kind,
            raw_path=args.output,
            state=state,
            collection_changed=True,
        )
        print(f"saved {args.key} run {run_id} to {args.output}")
        return 0
    except (ContractError, OSError) as exc:
        print(f"organic trend Apify run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
