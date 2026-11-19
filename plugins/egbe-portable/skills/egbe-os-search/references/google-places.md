# Google Places

Find businesses, inspect place details, and retrieve available Google reviews
through Egbe OS. Use this workflow for local business research and reputation
monitoring. It requires only the configured project's `OS_URL` and `OS_API_KEY`;
search, details, and reviews require the key's `tools` scope. Keep credentials
out of committed files. Read `GET /search/skill` and `GET /tools/skill` for the
current contracts before making requests.

## Setup

Check project identity and Places limits before spending:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits?resource=places" -fsS
```

## Search for a place

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/places" -fsS \
  -H "Content-Type: application/json" \
  -d '{"query":"Blue Bottle Coffee San Francisco","max_results":5}'
```

OS returns `{code, message, data}`. Read search rows from `data.results`:
`title` is the business name, `snippet` its address, `score` its star rating,
and `url` its Google Maps link. The stable provider ID is
`data.results[i].metadata.place_id`; `metadata.user_rating_count` holds the
rating count. Select the matching business by name, address, and geography
before using its ID below. Replace the example `place_id` in both requests
with that selected ID.

## Get reviews for a place

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/places/reviews" -fsS \
  -H "Content-Type: application/json" \
  -d '{"place_id":"ChIJ3UFdD2KAhYARYOHf4j7DshM"}'
```

Read `data.reviews` and `data.count` from the OS envelope. The response also
includes `data.place_id`, `data.name`, and aggregate rating information. Reviews
are normalized and ready to store: each has `id` (stable, source-prefixed
for dedup upsert), `source`, `business_id`, `author`, `rating`, `text`,
`publish_time`, `relative_time`, and `url` (direct Google Maps link to the review).

## Get full place details

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/places/details" -fsS \
  -H "Content-Type: application/json" \
  -d '{"place_id":"ChIJ3UFdD2KAhYARYOHf4j7DshM"}'
```

The OS envelope's `data` contains Google's place-details object, including
`id`, `displayName`, and requested fields. This differs from normalized search
rows and reviews. Pass optional `fields` (a comma-separated Places field mask,
such as `id,displayName,websiteUri`) to narrow the response; `language_code`
selects a localized response.

## Tool Parameters

| Endpoint | Body | Quota unit |
| --- | --- | --- |
| `POST /search/places` | `query` (required), `max_results` (1–20), `language_code`, `region_code` | `places:searches` |
| `POST /tools/places/details` | `place_id` (required), `fields`, `language_code` | `places:details` |
| `POST /tools/places/reviews` | `place_id` (required), `language_code` | `places:reviews` |

## Notes

- Google Places (New) returns **at most 5 reviews per place** (most relevant) —
  a hard API limit, not a bug. There is no full review history through this API.
- Each request consumes one quota unit of its resource; budgets reset daily.
- The API is **read-only**: it cannot post replies to reviews. Posting a reply
  requires the business owner's Google Business Profile, a separate authorized API.
- If the OS quota is exhausted, stop and report the exhausted resource rather
  than bypassing OS with direct Google credentials. Treat 401/403 as a project
  connection or scope problem; treat provider errors as failures, not empty
  search/review results. An empty `data.reviews` list means no reviews were
  returned, not that the business has no reviews.
