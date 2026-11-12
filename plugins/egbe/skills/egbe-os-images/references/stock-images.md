# Stock image search

Search Pixabay through OS using the existing project credentials:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/pixabay/search" -sS -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"ceramic workshop","image_type":"photo","orientation":"horizontal","safesearch":true,"per_page":10,"page":1}'
```

`data` contains `total` and `hits`. Each hit supplies `id`, `tags`,
`preview_url`, `large_url`, `page_url`, `width`, `height`, and `user`.
Inspect candidates for relevance, crop, resolution and visible brands/people.
Keep the selected image's source page and creator with the project's existing
asset records. Download the selected image into the product's assets rather
than depending on a temporary search-result URL.

Check the [Pixabay Content License](https://pixabay.com/service/license-summary/)
and the selected image's page for the intended use. Availability through the
API is not a blanket clearance for trademarks, recognizable people, resale or
implied endorsement.
