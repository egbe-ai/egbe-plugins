#!/usr/bin/env python3
"""Read-only, stdlib-only structural checks. No API calls or marketing verdicts."""
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

PHASES = ('readiness', 'creative-assembly', 'tracking', 'build-paused', 'launch',
          'edit', 'recovery', 'monitoring', 'pause')
ID = re.compile(r'^[A-Za-z0-9_-]{1,160}$')
SLUG = re.compile(r'^openai-[a-z0-9]+(?:-[a-z0-9]+)*$')


def ref(value):
    return value if isinstance(value, str) else ''


class Check:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.errors = []

    def fail(self, label, message):
        self.errors.append(f'{label}: {message}')

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            self.fail(str(relative), 'path must stay inside the product repository')
            return None
        return path

    def document(self, relative, required=True):
        path = self.path(relative)
        if path is None:
            return {}
        if not path.is_file() and not required:
            return {}
        try:
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                raise ValueError('expected a JSON object')
            return value
        except (OSError, ValueError) as exc:
            self.fail(str(relative), f'cannot read JSON object ({exc})')
            return {}

    def note(self, relative):
        path = self.path(relative)
        if path is not None and (not path.is_file() or not path.read_text().strip()):
            self.fail(str(relative), 'write a nonempty evidence note; record unknowns explicitly')

    def rows(self, doc, field, label):
        rows = doc.get(field)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            self.fail(label, f'{field} must be an array of objects')
            return []
        return rows

    def timestamp(self, value, label):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError()
        except (AttributeError, TypeError, ValueError):
            self.fail(label, 'use an observed ISO timestamp with timezone')


def tracked_url(check, value, slug, label):
    try:
        url = urlsplit(value)
        params = parse_qs(url.query)
        if url.scheme not in ('http', 'https') or not url.netloc:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        check.fail(label, 'expected an absolute HTTP(S) destination URL')
        return
    for key, expected in (('utm_source', 'openai'), ('utm_medium', 'paid_ai'), ('utm_campaign', slug)):
        if params.get(key) != [expected]:
            check.fail(label, f'{key} must occur once and equal {expected}')
    if len(params.get('utm_content', [])) != 1 or not params['utm_content'][0].strip():
        check.fail(label, 'include one nonempty utm_content')


def unique_ids(check, rows, label):
    result = {}
    for row in rows:
        value = row.get('id')
        if not isinstance(value, str) or not ID.fullmatch(value):
            check.fail(label, 'each object needs a valid provider id')
        elif value in result:
            check.fail(label, f'duplicate provider id {value}')
        else:
            result[value] = row
    return result


def execution(check, folder, slug, phase):
    state = check.document(folder / 'campaign-state.json', required=phase != 'recovery')
    if phase == 'recovery' and not state:
        # A create can be unconfirmed before any provider ID is known.
        return
    if state.get('channel') != 'openai' or state.get('campaign_slug') != slug:
        check.fail('campaign-state.json', 'channel/slug must match the campaign index')
    if not isinstance(state.get('product_slug'), str) or not state['product_slug'].strip():
        check.fail('campaign-state.json', 'product_slug is required')
    if state.get('status') not in ('paused', 'active', 'unknown', 'archived'):
        check.fail('campaign-state.json', 'status must be observed paused/active/archived or unknown')
    check.timestamp(state.get('updated_at'), 'campaign-state.json.updated_at')
    objects = state.get('objects') if isinstance(state.get('objects'), dict) else {}
    cid = objects.get('campaign_id')
    if not isinstance(cid, str) or not ID.fullmatch(cid):
        check.fail('campaign-state.json', 'objects.campaign_id must be a provider ID')
    groups = unique_ids(check, check.rows(objects, 'ad_groups', 'objects'), 'objects.ad_groups')
    ads = unique_ids(check, check.rows(objects, 'ads', 'objects'), 'objects.ads')
    files = objects.get('file_ids', [])
    if not isinstance(files, list) or any(not isinstance(v, str) or not ID.fullmatch(v) for v in files):
        check.fail('objects.file_ids', 'expected provider file IDs')
        files = []
    for group in groups.values():
        if group.get('campaign_id') != cid:
            check.fail('objects.ad_groups', f'{group["id"]} references a different campaign')
    for ad in ads.values():
        if ref(ad.get('ad_group_id')) not in groups or ad.get('file_id') not in files:
            check.fail('objects.ads', f'{ad["id"]} must reference a recorded group and file')
    if phase in ('monitoring', 'recovery'):
        return
    rb = check.document(folder / 'launch-readback.json')
    check.timestamp(rb.get('observed_at'), 'launch-readback.json.observed_at')
    campaign = rb.get('campaign') if isinstance(rb.get('campaign'), dict) else {}
    if campaign.get('id') != cid or campaign.get('status') != state.get('status'):
        check.fail('launch-readback.json', 'campaign ID/status differs from state; read OS, do not invent agreement')
    actual_groups = unique_ids(check, check.rows(rb, 'ad_groups', 'readback'), 'readback.ad_groups')
    actual_ads = unique_ids(check, check.rows(rb, 'ads', 'readback'), 'readback.ads')
    for value, observed in actual_groups.items():
        if value not in groups or observed.get('campaign_id') != cid:
            check.fail('readback.ad_groups', f'unexpected ID/parent for {value}')
    for value, observed in actual_ads.items():
        planned = ads.get(value, {})
        creative = observed.get('creative') if isinstance(observed.get('creative'), dict) else {}
        if value not in ads or observed.get('ad_group_id') != planned.get('ad_group_id'):
            check.fail('readback.ads', f'unexpected ID/parent for {value}')
        if creative.get('file_id') != planned.get('file_id'):
            check.fail('readback.ads', f'file binding differs for {value}')
        if phase in ('build-paused', 'launch'):
            tracked_url(check, creative.get('target_url'), slug, f'readback ad {value}')
    if phase in ('build-paused', 'launch'):
        if not groups or not ads or set(groups) != set(actual_groups) or set(ads) != set(actual_ads):
            check.fail('launch-readback.json', 'complete planned groups and ads must be observed')
        budget = state.get('budget') if isinstance(state.get('budget'), dict) else {}
        observed_budget = campaign.get('budget') if isinstance(campaign.get('budget'), dict) else {}
        try:
            amount = Decimal(str(budget.get('daily_budget_usd')))
            if not amount.is_finite() or amount <= 0 or budget.get('currency') != 'USD':
                raise ValueError()
            if amount * 1_000_000 != observed_budget.get('daily_spend_limit_micros'):
                check.fail('budget', 'daily USD budget differs from provider micros readback')
        except (InvalidOperation, ValueError):
            check.fail('budget', 'positive finite daily_budget_usd and USD currency required')
    if phase == 'build-paused' and any(x.get('status') != 'paused' for x in [campaign, *actual_groups.values(), *actual_ads.values()]):
        check.fail('build-paused', 'campaign and all planned children must be observed paused')
    if phase == 'launch':
        path = any(ad.get('status') == 'active' and actual_groups.get(ref(ad.get('ad_group_id')), {}).get('status') == 'active' for ad in actual_ads.values())
        if campaign.get('status') != 'active' or not path:
            check.fail('launch', 'expected observed active campaign → group → ad path; this is not proof of delivery')
    if phase == 'pause' and campaign.get('status') != 'paused':
        check.fail('pause', 'campaign must be observed paused; child flags need not be paused')


def operations(check, folder, phase):
    doc = check.document(folder / 'operations.json')
    keys, ids = set(), set()
    for item in check.rows(doc, 'operations', 'operations.json'):
        for field, seen in (('operation_id', ids), ('idempotency_key', keys)):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip() or value in seen:
                check.fail('operations.json', f'{field} must be nonempty and unique; update the existing entry on retries')
            elif field == 'idempotency_key' and len(value) > 128:
                check.fail('operations.json', 'idempotency_key exceeds API limit of 128')
            else:
                seen.add(value)
        path = item.get('path')
        if item.get('method') != 'POST' or not isinstance(path, str) or not path.startswith('/ads/openai/') or '/conversion-events' in path:
            check.fail('operations.json', 'record management POST paths relative to OS; customer event bodies stay in server storage')
        if not isinstance(item.get('payload'), dict):
            check.fail('operations.json', 'payload must preserve the exact request object ({} for no body)')
        status = item.get('status')
        if status not in ('prepared', 'unconfirmed', 'succeeded', 'failed'):
            check.fail('operations.json', 'invalid operation status')
        if phase == 'launch' and status in ('prepared', 'unconfirmed'):
            check.fail('operations.json', f'resolve {item.get("operation_id")} using its saved key before launch')


def validate(product_root, phase, campaign=None):
    check = Check(product_root)
    if phase not in PHASES:
        check.fail('phase', 'unsupported operation check')
        return check.errors
    base = Path('egbe-docs/marketing/campaigns/openai')
    if phase == 'readiness':
        doc = check.document(base / 'channel-readiness.json')
        if doc.get('channel') != 'openai' or not isinstance(doc.get('blockers'), list):
            check.fail('channel-readiness.json', 'channel=openai and blockers array required (unknowns are allowed)')
        check.timestamp(doc.get('checked_at'), 'readiness.checked_at')
        return check.errors
    index = check.document(base / 'campaigns.json')
    entries = check.rows(index, 'campaigns', 'campaigns.json')
    slug = campaign or index.get('selected_campaign')
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        check.fail('campaigns.json', 'select one safe openai-<slug> campaign')
        return check.errors
    matches = [entry for entry in entries if entry.get('campaign_slug') == slug]
    folder = base / slug
    if index.get('channel') != 'openai' or len(matches) != 1:
        check.fail('campaigns.json', 'channel=openai and exactly one matching campaign entry required')
        return check.errors
    if matches[0].get('campaign_path') != folder.as_posix() or matches[0].get('utm_campaign') != slug:
        check.fail('campaigns.json', 'campaign_path/utm_campaign must match the selected folder slug')
    plan_path = matches[0].get('plan_path')
    if phase in ('creative-assembly', 'build-paused', 'launch') and plan_path is not None:
        if not isinstance(plan_path, str) or not plan_path.strip() or Path(plan_path).is_absolute():
            check.fail('campaigns.json', 'plan_path must be a nonempty repository-relative path')
        else:
            check.note(plan_path)
    if phase in ('creative-assembly', 'build-paused', 'launch'):
        creative = check.document(folder / 'creatives.json')
        groups = check.rows(creative, 'ad_groups', 'creatives.json')
        ads = check.rows(creative, 'ads', 'creatives.json')
        group_slugs = [row.get('slug') for row in groups]
        if not groups or not ads:
            check.fail('creatives.json', 'at least one planned group and ad required')
        for ad in ads:
            if ad.get('ad_group_slug') not in group_slugs:
                check.fail('creatives.json', 'ad_group_slug must reference a planned group')
    if phase in ('tracking', 'build-paused', 'launch'):
        tracking = check.document(folder / 'tracking.json')
        tracked_url(check, tracking.get('destination_url'), slug, 'tracking.destination_url')
        if tracking.get('tracking_state') not in ('active', 'degraded', 'blocked'):
            check.fail('tracking.json', 'declare active/degraded/blocked, not inferred success')
    if phase in ('build-paused', 'launch', 'edit', 'recovery', 'monitoring', 'pause'):
        execution(check, folder, slug, phase)
    if phase in ('build-paused', 'launch', 'edit', 'recovery'):
        operations(check, folder, phase)
    if phase in ('build-paused', 'launch', 'edit', 'recovery', 'pause'):
        check.note(folder / 'change-log.md')
    if phase == 'monitoring':
        directory = check.path(folder / 'monitoring')
        notes = list(directory.glob('check-*.md')) if directory else []
        if not notes:
            check.fail('monitoring', 'write a timestamped check-*.md evidence note')
        for note in notes:
            check.note(note.relative_to(check.root))
    return check.errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-root', required=True)
    parser.add_argument('--campaign')
    parser.add_argument('--phase', choices=PHASES, required=True)
    args = parser.parse_args()
    errors = validate(args.product_root, args.phase, args.campaign)
    print(json.dumps({'ok': not errors, 'phase': args.phase, 'errors': errors}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
