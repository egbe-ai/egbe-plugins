#!/usr/bin/env python3
"""Versioned input adapters for the two current organic trend Apify actors."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from _contract import CANONICAL_PROVIDER_RUNS, ContractError, collection_parameters, parse_rfc3339


INPUT_CONTRACT_VERSION = "apify-inputs-v1"
TIKTOK_TRANSCRIPT_MODE = "DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES"


def collection_window(context: dict[str, Any], reference_at: str) -> dict[str, Any]:
    parameters = collection_parameters(context)
    reference = parse_rfc3339(reference_at, "collection reference_at")
    try:
        oldest = (reference.date() - timedelta(days=parameters["lookback_days"])).isoformat()
    except (OverflowError, ValueError) as exc:
        raise ContractError("collection lookback_days exceeds the supported calendar") from exc
    return {**parameters, "reference_at": reference_at, "oldest_post_date": oldest}


def validate_collection_window(context: dict[str, Any], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value != collection_window(context, value.get("reference_at")):
        raise ContractError("saved collection window does not match context")
    return value


def build_discovery_inputs(
    accounts: list[dict[str, Any]], context: dict[str, Any], window: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    parameters = collection_parameters(context)
    if window is not None:
        validate_collection_window(context, window)
    lower_bound = window["oldest_post_date"] if window else f"{parameters['lookback_days']} days"
    if not 1 <= len(accounts) <= 6:
        raise ContractError("discovery requires 1–6 accounts")
    handles: dict[str, list[str]] = {"tiktok": [], "instagram": []}
    for index, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise ContractError(f"accounts[{index}] must be an object")
        platform = account.get("platform")
        handle = account.get("handle")
        if platform not in handles or not isinstance(handle, str) or not handle.strip():
            raise ContractError(f"accounts[{index}] has invalid platform or handle")
        normalized = handle.strip().lstrip("@")
        if normalized not in handles[platform]:
            handles[platform].append(normalized)
    result: dict[str, dict[str, Any]] = {}
    if handles["tiktok"]:
        result["tiktok-discovery"] = {
            "profiles": handles["tiktok"],
            "resultsPerPage": parameters["discovery_limit_per_account"],
            "profileSorting": "latest",
            "oldestPostDateUnified": lower_bound,
        }
    if handles["instagram"]:
        result["instagram-discovery"] = {
            "username": handles["instagram"],
            "resultsLimit": parameters["discovery_limit_per_account"],
            "onlyPostsNewerThan": lower_bound,
        }
    return result


def build_enrichment_inputs(videos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, list[str]] = {"tiktok": [], "instagram": []}
    for index, video in enumerate(videos):
        if not isinstance(video, dict) or not video.get("selected_for_analysis"):
            continue
        if video.get("time_window_status") != "in_window":
            raise ContractError("enrichment selected an observation outside the time-window sample")
        platform = video.get("platform")
        url = video.get("url")
        if platform not in selected or not isinstance(url, str) or not url.startswith("https://"):
            raise ContractError(f"videos[{index}] has invalid selected platform or URL")
        if url not in selected[platform]:
            selected[platform].append(url)
    if sum(len(urls) for urls in selected.values()) > 30:
        raise ContractError("enrichment exceeds the v1 maximum of 30 selected videos")
    result: dict[str, dict[str, Any]] = {}
    if selected["tiktok"]:
        result["tiktok-enrichment"] = {
            "postURLs": selected["tiktok"],
            "shouldDownloadVideos": True,
            "downloadSubtitlesOptions": TIKTOK_TRANSCRIPT_MODE,
            "commentsPerPost": 20,
        }
    if selected["instagram"]:
        result["instagram-enrichment"] = {
            "username": selected["instagram"],
            "includeSharesCount": True,
            "includeTranscript": True,
            "includeDownloadedVideo": True,
        }
    return result


def validate_provider_input(logical_key: str, value: dict[str, Any]) -> None:
    contract = CANONICAL_PROVIDER_RUNS.get(logical_key)
    if contract is None:
        raise ContractError("unknown provider logical key")
    expected_keys = set(contract["input_keys"])
    if set(value) != expected_keys:
        raise ContractError(
            f"{logical_key} input keys must be exactly {sorted(expected_keys)}"
        )
    if logical_key == "tiktok-discovery":
        profiles = value["profiles"]
        if not isinstance(profiles, list) or not 1 <= len(profiles) <= 6:
            raise ContractError("TikTok discovery profiles must contain 1–6 handles")
        _validate_discovery_scope(value["resultsPerPage"], value["oldestPostDateUnified"])
        if value["profileSorting"] != "latest":
            raise ContractError("TikTok discovery must request latest videos")
    elif logical_key == "instagram-discovery":
        usernames = value["username"]
        if not isinstance(usernames, list) or not 1 <= len(usernames) <= 6:
            raise ContractError("Instagram discovery usernames must contain 1–6 handles")
        _validate_discovery_scope(value["resultsLimit"], value["onlyPostsNewerThan"])
    elif logical_key == "tiktok-enrichment":
        urls = value["postURLs"]
        if not isinstance(urls, list) or not 1 <= len(urls) <= 30:
            raise ContractError("TikTok enrichment must contain 1–30 post URLs")
        if (
            value["shouldDownloadVideos"] is not True
            or value["downloadSubtitlesOptions"] != TIKTOK_TRANSCRIPT_MODE
            or value["commentsPerPost"] != 20
        ):
            raise ContractError("TikTok enrichment media/transcript/comment settings are invalid")
    else:
        urls = value["username"]
        if not isinstance(urls, list) or not 1 <= len(urls) <= 30:
            raise ContractError("Instagram enrichment must contain 1–30 Reel URLs")
        if not all(
            value[field] is True
            for field in ("includeSharesCount", "includeTranscript", "includeDownloadedVideo")
        ):
            raise ContractError("Instagram enrichment add-ons must be enabled")
    list_field = (
        "profiles"
        if logical_key == "tiktok-discovery"
        else "postURLs"
        if logical_key == "tiktok-enrichment"
        else "username"
    )
    if not all(isinstance(item, str) and item.strip() for item in value[list_field]):
        raise ContractError(f"{logical_key} input identifiers must be non-empty strings")


def _validate_discovery_scope(limit: Any, lower_bound: Any) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 30:
        raise ContractError("discovery limit per account must be an integer from 1 to 30")
    if isinstance(lower_bound, str):
        days, separator, unit = lower_bound.partition(" ")
        if separator and unit == "days" and days.isdecimal() and int(days) > 0:
            return
        try:
            if date.fromisoformat(lower_bound).isoformat() == lower_bound:
                return
        except ValueError:
            pass
    raise ContractError("discovery lower bound must be an ISO date or a positive number of days")
