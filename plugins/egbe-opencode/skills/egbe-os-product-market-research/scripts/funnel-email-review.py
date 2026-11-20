"""Finite, attributable mailbox review for a physical research funnel.

This is a local resource shared by 05 and its 02 mailbox adapter. A closed
coverage gap never asserts that a website result or verification was observed.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

HARVEST_AFTER_DAYS = 14  # existing Lifecycle Capture observation window


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def review(subscription, document, *, now=None, harvest_after_days=HARVEST_AFTER_DAYS):
    now = now or datetime.now().astimezone()
    fid, alias = subscription["funnel_id"], subscription["alias"]
    submissions = subscription.get("submission_checks") or [{
        "submission_ref": subscription.get("submission_ref"), "path_id": path,
        "submitted_at": subscription.get("submitted_at") or subscription["subscribed_on"] + "T00:00:00" + now.strftime("%z"),
        "campaign_refs": subscription["campaign_refs"], "confirmed": subscription.get("confirmed") is True,
    } for path in subscription["path_refs"]]
    checks = [check for check in document.get("checks", []) if isinstance(check, dict)
              and check.get("funnel_id") == fid and check.get("alias") == alias
              and check.get("query_succeeded") is True and timestamp(check.get("checked_at")) is not None
              and timestamp(check["checked_at"]) <= now
              and str(check.get("source_ref") or "").startswith("inbox_snapshot:")]
    gaps, pending_reasons, observed_checks, unknown, missing = [], [], [], [], []
    deadlines, post_checks, expected = [], [], False
    events = [event for event in document.get("events", []) if isinstance(event, dict)
              and event.get("funnel_id") == fid and event.get("alias") == alias
              and timestamp(event.get("occurred_at")) is not None and timestamp(event["occurred_at"]) <= now]
    for submission in submissions:
        submitted = timestamp(submission.get("submitted_at"))
        if submitted is None:
            pending_reasons.append("submission_time_unknown")
            continue
        campaign_refs = set(submission.get("campaign_refs") or [])
        path_id = submission.get("path_id")
        attributable = [check for check in checks if path_id in (check.get("path_refs") or [])
                        and campaign_refs.intersection(check.get("campaign_refs") or [])
                        and timestamp(check["checked_at"]) >= submitted]
        same_day = [check for check in attributable if timestamp(check["checked_at"]).date()
                    == submitted.astimezone(timestamp(check["checked_at"]).tzinfo).date()]
        path_gaps = []
        if same_day:
            observed_checks.extend(same_day)
        elif now.date() <= submitted.astimezone(now.tzinfo).date():
            pending_reasons.append("same_day_mail_check_missing")
        else:
            path_gaps.append("same_day_check_missed")
        post_checks.extend(attributable)
        expectations = submission.get("email_expectations", subscription.get("email_expectations")) or {}
        expected = expected or any(expectations.get(key) is True for key in ("confirmation", "result"))
        local_submitted = submitted.astimezone(now.tzinfo)
        deadline = timestamp(expectations.get("wait_until")) or datetime.combine(
            local_submitted.date() + timedelta(days=harvest_after_days), time.min, tzinfo=now.tzinfo)
        # An earlier message, even to the same alias, cannot stand in for a
        # result or verification after this separately approved submission.
        relevant = [event for event in events if event.get("path_id") in (None, path_id)
                    and campaign_refs.intersection(event.get("campaign_refs") or [])
                    and timestamp(event["occurred_at"]) >= submitted]
        confirmed = submission.get("confirmed") is True or any(event.get("type") == "email_confirmation"
                    and event.get("verification_status") == "confirmed" for event in relevant)
        result_received = any(event.get("type") == "email_result" for event in relevant)
        path_missing = [key for key, observed in (("confirmation", confirmed), ("result", result_received))
                        if expectations.get(key) is True and not observed]
        path_unknown = [key for key in ("confirmation", "result") if expectations.get(key) is None]
        unknown.extend(path_unknown)
        missing.extend(path_missing)
        if path_unknown and attributable:
            path_gaps.append("email_expectation_undetermined")
        elif path_unknown and not path_gaps:
            pending_reasons.append("email_expectations_unknown")
        if path_missing:
            deadlines.append(deadline)
            boundary_checked = any(timestamp(check["checked_at"]) >= deadline for check in attributable)
            if now < deadline or not boundary_checked:
                pending_reasons.append("confirmation_required" if "confirmation" in path_missing and
                    any(event.get("type") == "email_confirmation" for event in relevant) else "email_not_received")
            else:
                path_gaps.extend("confirmation_unverified" if key == "confirmation" else "expected_email_not_received" for key in path_missing)
        gaps.extend(path_gaps)
    latest_check = max(post_checks, key=lambda item: timestamp(item["checked_at"]), default=None)
    status = "pending" if pending_reasons else "coverage_gap" if gaps else "expected_email_observed" if expected else "reviewed_no_expected_email"
    return {"status": status, "pending": bool(pending_reasons), "detail": pending_reasons[0] if pending_reasons else gaps[0] if gaps else status,
            "gaps": list(dict.fromkeys(gaps)), "unknown": list(dict.fromkeys(unknown + missing)),
            "checked_at": latest_check.get("checked_at") if latest_check else None,
            "source_ref": latest_check.get("source_ref") if latest_check else None,
            "same_day_checked_at": min((check["checked_at"] for check in observed_checks), key=timestamp, default=None),
            "wait_until": max(deadlines).isoformat() if deadlines else None}
