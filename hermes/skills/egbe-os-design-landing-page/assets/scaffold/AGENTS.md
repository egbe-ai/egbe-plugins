<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Platform scaffold setup and ownership

This scaffold supplies Sentry, the base Umami tracker and the session recorder,
but its empty `src/lib/egbe-observability.generated.ts` does not configure a
project. Inspect the actual generated identifiers and the project's existing
Analytics and Errors bindings before publishing. Use `egbe-os-analytics` and
`egbe-os-errors` to configure missing bindings, then populate the generated file
with their public identifiers and snippets. Keep server credentials out of it.

Reuse valid existing bindings and preserve their generated identifiers; do not
reprovision a configured project or rotate identifiers merely because this
scaffold was copied. Session recording is required: preserve both scripts with
100% sampling, moderate masking, and a 30-minute maximum recording duration.
Preserve `instrumentation-client.ts`, `instrumentation.ts`, the Sentry config
files, `EgbeAnalytics`, and `egbe-observability.generated.ts`.

Product implementation may add canonical analytics events to real interaction
points. Verify the configured integration through the capabilities' readback;
the presence of these files or a successful build is not delivery proof.

Preserve the session-recording disclosure in `/privacy`, link it from the product
footer, and extend the page for the product's actual data handling. Keep private
displayed content out of recordings with the recorder's `data-block-selector`
when adding sensitive product surfaces; input masking alone does not hide all
text displayed on the page.
