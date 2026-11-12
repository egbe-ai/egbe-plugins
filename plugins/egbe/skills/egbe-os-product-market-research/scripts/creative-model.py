"""Individual ad records, scoped pattern proof and faithful report projections."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import hashlib
import importlib.util
from pathlib import Path
import html
import json
import posixpath
import re
import urllib.parse
from collections import defaultdict
from typing import Any


_spec = importlib.util.spec_from_file_location("pmr_creative_selection", Path(__file__).with_name("creative-selection.py"))
SELECTION = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SELECTION)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def creative_type(row: dict) -> str:
    form = row.get('format_kind')
    if form == 'text_only':
        return 'text'
    if form == 'video':
        return 'video'
    if form in {'static_image', 'carousel', 'dynamic', 'meme'}:
        return 'static_image'
    return 'unknown'


def duration_proven(row: dict, days=None) -> bool:
    """Whether a native, scoped delivery duration is actually available."""
    value = row.get("served_days")
    return (type(value) is int and value >= 0 and row.get("age_basis") == "platform_dates"
            and bool(row.get("country")) and row.get("duration_scope") in ("country", "global")
            and ("date_scope" not in row or row.get("date_scope") == "global"
                 or (row.get("date_scope") == "country" and row.get("date_country") == row["country"])))


def status(row: dict, days: int) -> str:
    active = row.get('running_at_capture')
    return 'active' if active is True else 'stopped' if active is False else 'unknown'


def individual_ads(rows: list[dict], days: int) -> list[dict]:
    """One native ad per market and channel, retaining delivery observations."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        row['native_ad_id'] = str(row.get('native_ad_id') or row.get('ad_id') or row['creative_id'])
        key = (row.get('domain'), row.get('platform'), row.get('channel'), row['native_ad_id'], row.get('country'))
        groups[key].append(row)

    def observed_key(row):
        return (str(row.get('last_observed') or row.get('retrieved_on') or row.get('last_seen') or ''),
                str(row.get('last_seen') or ''), row.get('running_at_capture') is True, digest(row))

    fields = ('source', 'headline', 'body', 'image_url', 'media_urls', 'video_url', 'first_seen', 'last_seen',
              'served_days', 'running_at_capture', 'age_basis', 'duration_scope', 'country',
              'first_observed', 'last_observed', 'retrieved_on', 'date_scope', 'date_country',
              'activity_scope', 'activity_country', 'native_activity_status', 'placement')
    out = []
    variants: dict[tuple, set] = defaultdict(set)
    variant_keys = {}
    for key, observations in groups.items():
        # A listing or global date cannot overwrite a country delivery record.
        # Choose one coherent native observation; never add durations or borrow
        # activity from another scope to complete its proof.
        scoped = [row for row in observations if row.get('duration_scope') == 'country'
                  and row.get('age_basis') == 'platform_dates' and type(row.get('served_days')) is int]
        native = [row for row in observations if row.get('age_basis') == 'platform_dates'
                  and row.get('duration_scope') in ('country', 'global')]
        # A qualifying native run is kept even when a shorter country record
        # exists: a qualifying country run first (its dates and activity stay
        # together), otherwise the longest qualifying global run. Spans are
        # never added.
        qualifying = [row for row in native if duration_proven(row, days)]
        if qualifying:
            row = dict(max(qualifying, key=lambda r: (r.get('duration_scope') == 'country', r['served_days'], observed_key(r))))
        else:
            row = dict(max(scoped or native or observations, key=observed_key))
        row['creative_id'] = f"{row.get('platform')}:{row['native_ad_id']}:{row.get('country') or 'unscoped'}:{digest(row.get('domain'))}"
        # Display and search may share Google's native ID in one market.
        # Keep primary-channel IDs stable, distinguishing other placements.
        channel = row.get('channel')
        if channel and channel not in {row.get('platform'), f"{row.get('platform')}_ads"}:
            row['creative_id'] += f":{channel}"
        row['observations'] = []
        row['media_assets'], row['source_members'] = [], []
        for observation in sorted(observations, key=observed_key):
            for version in observation.get('observations') or [{name: observation.get(name) for name in fields}]:
                if version not in row['observations']:
                    row['observations'].append(version)
            for name in ('media_assets', 'source_members'):
                for value in observation.get(name) or []:
                    if value not in row[name]:
                        row[name].append(value)
        # Match the Footprint policy: contradictory country-native activity is
        # unresolved. An active tie-break or activity in another scope cannot
        # turn this ad into current-use proof.
        native_activity = set()
        for observation in observations:
            for version in observation.get('observations') or [observation]:
                if version.get('country') == row.get('country'):
                    activity = version.get('native_activity_status') or version.get('activity_status') or version.get('status')
                    if activity:
                        native_activity.add(activity)
        if native_activity & {'active', 'recent', 'recent_delivery'} and native_activity & {'stopped', 'inactive', 'ended', 'archived'}:
            row['running_at_capture'] = None
            row['activity_status'] = 'mixed'
            row['current_activity_conflict'] = sorted(native_activity)
        row['creative_type'] = creative_type(row)
        row['longevity_status'] = status(row, days)
        row['native_global_duration_available'] = any(
            type(item.get('served_days')) is int and item['served_days'] >= 0
            and item.get('age_basis') == 'platform_dates' and item.get('duration_scope') == 'global'
            for item in observations)
        row['relaunched'], row['fingerprint_span_days'] = False, None
        copy = ' '.join(str(row.get(name) or '') for name in ('headline', 'body')).strip().casefold()
        group = (row.get('domain'), row.get('channel'), row.get('country'), copy or row['creative_id'])
        row['variant_group_id'] = digest(group)
        variant_keys[row['creative_id']] = group
        variants[group].add(row['native_ad_id'])
        out.append(row)
    for row in out:
        row['variants'] = len(variants[variant_keys[row['creative_id']]])
        row['strength_components'] = {'running': row.get('running_at_capture'), 'served_days': row.get('served_days'),
                                      'duration_scope': row.get('duration_scope'), 'variants': row['variants'],
                                      'reach': row.get('eu_total_reach'), 'reach_source': row.get('source'),
                                      'reach_country': row.get('country')}
    return out


def strength_key(row: dict) -> tuple:
    return SELECTION.strength_key(row)


def eligible(row: dict) -> bool:
    return SELECTION.eligible(row)


def patterns(creatives: list[dict], labels: list[dict], taxonomy: dict, days: int, dictionary: dict | None = None) -> list[dict]:
    by_id = {row['creative_id']: row for row in creatives}
    dictionary = dictionary or {}
    families = {row['message_family_id']: row for row in dictionary.get('message_families', [])}
    angles = {row['angle_id']: row for row in dictionary.get('angles', [])}
    groups: dict[tuple, list] = defaultdict(list)
    for label in labels:
        row = by_id.get(label.get('creative_id'))
        if not row or not eligible(row) or row.get('creative_type') == 'unknown':
            continue
        scope = (row.get('country'), row['channel'], row['creative_type'], (row.get('format_kind'), row.get('format_detail') or 'unspecified'))
        family = row.get('message_family_id')
        if family:
            groups[scope + ('message_family', family)].append((row, label))
        for angle in row.get('category_angle_ids') or []:
            if not family:
                continue
            # An angle is paired with offer and family, rather than collapsing
            # unrelated offers into a broad buyer or benefit label.
            groups[scope + ('angle', angle, (label.get('labels') or {}).get('offer_kind'), family)].append((row, label))
    results = []
    for key, members in groups.items():
        country, channel, ctype, form, level, identity = key[:6]
        by_domain: dict[str, list] = defaultdict(list)
        for creative, label in members:
            by_domain[creative['domain']].append(creative)
        proving = {domain for domain, items in by_domain.items() if any(duration_proven(c, days) for c in items)}
        running = {domain for domain, items in by_domain.items() if any(c.get('running_at_capture') is True for c in items)}
        stopped = any(c.get('running_at_capture') is False for c, _ in members)
        pattern_status = 'active' if running else 'stopped' if stopped else 'observed'
        definition = families.get(identity, {}) if level == 'message_family' else angles.get(identity, {})
        definition = {k: v for k, v in definition.items() if k not in ('members', 'support')}
        description = definition.get('meaning') or definition.get('label') or identity
        direct = {d for d in by_domain if any(c.get('competitor_tier') == 'direct' for c in by_domain[d])}
        indirect = {d for d in by_domain if any(c.get('competitor_tier') == 'indirect' for c in by_domain[d])}
        lineage = []
        for c, _ in sorted(members, key=lambda m: strength_key(m[0])):
            lineage.append({k: c.get(k) for k in ('creative_id', 'native_ad_id', 'domain', 'country', 'countries',
                           'channel', 'competitor_tier', 'relevance', 'duration_scope', 'served_days', 'running_at_capture',
                           'first_seen', 'last_seen', 'longevity_status', 'footprint_ad_id', 'source_members')})
        results.append({'type': 'pattern_score', 'pattern_id': digest(key), 'pattern_level': level,
                        'pattern_key': {'message_family_id': identity} if level == 'message_family' else {'angle_id': identity, 'offer_kind': key[6], 'message_family_id': key[7]},
                        'country': country, 'channel': channel, 'creative_type': ctype, 'format_kind': form[0], 'format_detail': form[1],
                        'description': description, 'message_family': definition if level == 'message_family' else {k:v for k,v in families.get(key[7], {}).items() if k not in ('members','support')},
                        'angles': [{k:v for k,v in angles[a].items() if k not in ('members','support')} for a in sorted({a for c, _ in members for a in c.get('category_angle_ids', [])}) if a in angles],
                        'pattern_status': pattern_status, 'convergence': len(by_domain), 'direct_convergence': len(direct),
                        'indirect_convergence': len(indirect), 'recurring': len(by_domain) > 1,
                        'competitors': sorted(by_domain), 'dated_competitors': sorted(proving), 'running_competitors': sorted(running),
                        'creatives': len(members), 'members': lineage, 'source_members': [source for c, _ in members for source in (c.get('source_members') or [{k:c.get(k) for k in ('creative_id','domain','country','countries','channel','competitor_tier','relevance','language_allowed','language_status','duration_scope','served_days','running_at_capture','footprint_ad_id')}])], 'relevance': 'relevant', 'language_status': 'allowed', 'language_allowed': True,
                        'max_served_days': max((c.get('served_days') or 0 for c, _ in members), default=0) or None,
                        'examples': {'hook_text': list(dict.fromkeys((cl.get('texts') or {}).get('hook_text') for _, cl in members if (cl.get('texts') or {}).get('hook_text')))[:3]},
                        'market_scope': members[0][0].get('market_scope'),
                        'category_dictionary_sha256': dictionary.get('dictionary_sha256'), 'tier': 'B'})
    return sorted(results, key=lambda row: (str(row['country']), row['channel'], row['creative_type'], row['pattern_id']))


_COMMERCIAL = re.compile(r'[$€£]\s*\d|\d\s*(?:USD|EUR|GBP)|\d+\s?%\s?off|\bsalar(?:y|ies)\b|\bearn\b|\bguarantee\b', re.I)


def promises(creatives: list[dict], classifications: list[dict] | None = None) -> list[dict]:
    """Whole source sentences for commercial terms and grounded outcome promises.

    The taxonomy's promise excerpt locates a claim; it is never used as the
    report text when the corresponding complete sentence is available.
    """
    rows: dict[tuple, dict] = {}
    by_id = {row.get('creative_id'): row for row in classifications or []}
    for creative in creatives:
        texts = [(creative.get(k), k, 'native_ad_copy', []) for k in ('headline', 'body')]
        texts += [(creative.get('transcript'), 'transcript', 'transcript', [])]
        snippets = creative.get('observed_text_sources') or []
        if snippets:
            texts += [(item.get('text'), 'observed_text', item.get('excerpt_source') or 'unknown_extraction',
                       item.get('frame_refs') or []) for item in snippets if isinstance(item, dict)]
        else:
            origin = creative.get('observed_text_source')
            excerpt_source = 'native_ad_copy' if origin == 'native_text' else 'frame_extraction' if origin == 'frame_extraction' else 'unknown_extraction'
            texts += [(creative.get('observed_text'), 'observed_text', excerpt_source,
                       creative.get('observed_text_frame_refs') or [])]
        for index, text in enumerate(creative.get('extra_texts') or []):
            origins = creative.get('extra_text_sources') or []
            origin = origins[index] if index < len(origins) and isinstance(origins[index], dict) else {'kind': 'ad_text'}
            kind = origin.get('kind')
            source = ('frame_extraction' if kind == 'video_frame_ocr' else 'video_metadata'
                      if str(kind).startswith('video_metadata') else 'native_ad_copy' if kind == 'ad_text' else 'unknown_extraction')
            refs = [origin['ref']] if source == 'frame_extraction' and origin.get('ref') else []
            texts.append((text, 'extra_texts', source, refs))
        texts += [(observation.get(k), 'native_observation', 'native_ad_copy', [])
                  for observation in creative.get('observations') or [] for k in ('headline', 'body')]
        texts += [(observation.get(k), 'native_observation', 'native_ad_copy', [])
                  for observation in creative.get('source_observations') or [] for k in ('title', 'body')]
        metadata = creative.get('video_metadata') or {}
        texts += [(metadata.get(k), 'video_metadata_' + k, 'video_metadata', []) for k in ('title', 'description')]
        analysis = creative.get('media_analysis') or {}
        analysis = analysis.get('analysis') or analysis
        for frame in analysis.get('frames') or []:
            ref = frame.get('ref') or frame.get('frame_ref')
            refs = [ref] if ref else []
            texts += [(text, 'video_frame', 'frame_extraction', refs) for text in frame.get('visible_text') or []]
        label = by_id.get(creative['creative_id']) or {}
        extracted = (label.get('texts') or {}).get('promise_text')
        extracts = [(extracted, 'outcome_promise')] if isinstance(extracted, str) and extracted.strip() else []
        for promise in (label.get('semantics') or {}).get('promises') or []:
            if isinstance(promise, dict) and isinstance(promise.get('excerpt'), str):
                extracts.append((promise['excerpt'], promise.get('kind') or 'outcome_promise'))

        def normalized(value: str) -> str:
            return re.sub(r'\s+', ' ', value).strip().casefold()

        for text, source, excerpt_source, frame_refs in texts:
            if not isinstance(text, str):
                continue
            # OCR/speech line wraps do not constitute sentence boundaries.
            sentences = [part.strip() for part in re.split(r'(?<=[!?])\s+|(?<=\.)\s+(?=[A-ZА-Я])',
                                                          re.sub(r'\s+', ' ', text).strip()) if part.strip()]
            claims = [(sentence, 'commercial_terms') for sentence in sentences if _COMMERCIAL.search(sentence)
                      or re.search(r'\b(?:save|discount)\s+\d+(?:\.\d+)?\s*%', sentence, re.I)]
            for extracted, kind in extracts:
                if not extracted.strip() or normalized(extracted) not in normalized(text):
                    continue
                candidates = []
                # An excerpt can span punctuation; expand to complete source
                # sentences rather than cropping a fixed context window.
                for start in range(len(sentences)):
                    for end in range(start + 1, min(len(sentences), start + 3) + 1):
                        candidate = ' '.join(sentences[start:end])
                        if normalized(extracted) in normalized(candidate):
                            candidates.append(candidate)
                if candidates:
                    claims.append((min(candidates, key=len), kind))
                else:
                    claims.append((re.sub(r'\s+', ' ', text).strip(), kind))
            for sentence, kind in claims:
                key = (creative['domain'], re.sub(r'\s+', ' ', sentence).casefold())
                row = rows.setdefault(key, {'type': 'price_anchor', 'domain': creative['domain'], 'platform': creative['platform'],
                                          'creative_id': creative['creative_id'], 'excerpt': sentence, 'promise_kind': 'competitor_claim',
                                          'claim_kinds': [],
                                          'source_refs': [], 'country': creative.get('country'), 'relevance': creative.get('relevance'),
                                          'market_scope': creative.get('market_scope'), 'usage': 'information_only', 'tier': 'B'})
                if kind not in row['claim_kinds']:
                    row['claim_kinds'].append(kind)
                ref = {'creative_id': creative['creative_id'], 'source_kind': source, 'country': creative.get('country'),
                       'excerpt_source': excerpt_source, 'frame_refs': frame_refs}
                if ref not in row['source_refs']:
                    row['source_refs'].append(ref)
    return sorted(rows.values(), key=lambda row: (row['domain'], row['excerpt']))


def markdown_literal(value: Any, *, inline: bool = False) -> str:
    text = str(value or '')
    if inline:
        text = ' '.join(text.split())
    text = html.escape(text, quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+|~])', lambda match: '\\' + match.group(0), text)


def markdown_quote(value: Any) -> str:
    return '\n'.join('> ' + markdown_literal(line) for line in str(value or '').splitlines())


def markdown_link(label: Any, url: Any) -> str:
    label = markdown_literal(label, inline=True)
    url = str(url or '')
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or any(ord(char) < 33 for char in url):
            return label + ' (link unavailable)'
    except ValueError:
        return label + ' (link unavailable)'
    return f"[{label}]({urllib.parse.quote(url, safe=':/?=&%+@;,-._~#')})"


def section(creatives: list[dict], patterns: list[dict], claims: list[dict], coverage: list[dict], days: int, selection: dict | None = None) -> str:
    lines = ['### Creative inspection sample by market, channel and type', '',
             'Stable-ID inspection sample of comparable creatives. Dates, native activity and variants are observations, not measured conversions, return on spend or selection advice.', '']
    by_id = {row['creative_id']: row for row in creatives}
    for cell in selection["cells"] if selection is not None else SELECTION.top_cells(creatives):
        country, channel, ctype, domain = (cell.get(key) or 'unscoped' for key in ('country', 'channel', 'creative_type', 'domain'))
        lookup = {row['creative_id']: row for row in creatives if row.get('country') == cell['country'] and row.get('channel') == cell['channel'] and row.get('domain') == cell['domain'] and row.get('creative_type', 'unknown') == cell['creative_type']}
        items = [lookup[cid] for cid in cell['creative_ids']]
        lines += [f'#### {country} / {channel} / {ctype} / {domain}', '']
        for row in items:
            available = [row.get(k) for k in ('headline', 'body', 'observed_text', 'transcript')] + (row.get('extra_texts') or [])
            text = '\n\n'.join(dict.fromkeys(str(value) for value in available if value))
            lines += [f"- {markdown_link(row['creative_id'], row.get('link'))}: {row.get('served_days') if row.get('served_days') is not None else 'unknown'} days ({row.get('age_basis') or 'unknown'}, {row.get('duration_scope') or 'unscoped'}); running: {row.get('running_at_capture')}; format: {row.get('format_kind') or 'unknown'} / {row.get('format_detail') or 'unspecified'}.", '', markdown_quote(text or 'No readable text extracted.'), '']
            assets = [a for a in row.get('media_assets') or [] if a.get('publication_status') != 'unavailable']
            previews = [a for a in assets if a.get('kind') in ('image', 'preview')]
            if not previews:
                previews = [a for a in assets if a.get('kind') == 'frame'][:1]
            for asset in previews:
                # Materialized report is egbe-docs/research/market/full-report.md.
                ref = posixpath.relpath(asset['path'], _artifact_path('egbe-docs/research/market'))
                lines += [f"![Creative preview]({ref})", '']
            if row.get('video_gaps'):
                lines += ['Video gaps: ' + markdown_literal('; '.join(row['video_gaps']), inline=True), '']
    lines += ['### Patterns by market, channel, creative type and format', '']
    for row in patterns:
        lines += [f"- {row.get('country') or 'unscoped'} / {row['channel']} / {row['creative_type']} / {row['format_kind']} / {row.get('format_detail') or 'unspecified'}: **{markdown_literal(row['description'], inline=True)}**. {row['pattern_status']}; convergence {row['convergence']} (direct {row['direct_convergence']}); competitors: {', '.join(row['competitors'])}."]
        for member in row['members'][:3]:
            creative = by_id.get(member['creative_id'], {})
            lines.append(f"  - Example: {markdown_link(member['creative_id'], creative.get('link'))}")
    lines += ['', '### Competitor promises and price anchors', '', 'Observed competitor claims are information only.', '']
    previous_domain = None
    for claim in claims:
        if claim['domain'] != previous_domain:
            lines += [f"#### {claim['domain']}", '']
            previous_domain = claim['domain']
        sources = ', '.join(f"{markdown_link(ref['creative_id'], by_id.get(ref['creative_id'], {}).get('link'))} ({ref.get('country') or 'unscoped'}; {markdown_literal(ref.get('excerpt_source') or ref.get('source_kind') or 'unknown', inline=True)})" for ref in claim.get('source_refs') or [])
        lines += [f"- {markdown_literal(claim['excerpt'], inline=True)} ({claim.get('relevance') or 'unknown'}). Sources: {sources}"]
    lines += ['', '### Method and coverage', '', 'Native delivery intervals retain their source scope. Separate launches and listing sightings do not establish continuous delivery or commercial success.', '']
    for gap in coverage:
        lines.append(f"- {gap.get('country') or 'unscoped'} / {gap.get('channel') or gap.get('source')} / {gap.get('domain', 'all')}: {gap.get('status')}; {markdown_literal(gap.get('detail'), inline=True)}")
    return '\n'.join(lines) + '\n'
