---
name: egbe-os-product-market-research
description: Collect and analyze product-market evidence for a bounded research assignment, with source provenance and resumable execution.
metadata:
  egbe-when: "Use for scoped customer, competitor, demand, channel or economic evidence collection and analysis."
  egbe-visible: "true"
  egbe-title: "Market research"
  egbe-description: "Collect reliable market evidence and answer the project's research question."
  egbe-category: "Product & design"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Code can also be published without the shell by
committing through the connector (`egbe-os-git`, "Without a terminal"). Until
the shell step or that commit and its deploy succeed, do not report the work as
published: a Claude Artifact or a local preview is not an Egbe deployment.


# Product Market Research

Execute a bounded research assignment prepared from the user's task and relevant
project evidence. The calling method owns the question: Market and acquisition
for a market decision, Product for a value or diagnosis question, or the current
task for a narrow operation. It owns sufficient depth, comparative criteria and the
next business decision. PMR owns reliable collection, source integrity and the
requested analysis. Comparing, synthesizing, ranking and conditional conclusions
are allowed within the assignment; they are not authority to choose a new goal,
test, budget or approval policy.

The assignment states the question, relevant known evidence, consequential gaps,
requested result and applicable constraints. For substantial research, use its
brief at `egbe-docs/research/<id>/brief.md`; a narrow operation can use existing
task text or explicit CLI inputs. No fixed headings or full questionnaire are
required. Clarify missing operational inputs within that question, without
choosing a new product strategy. Reuse evidence and collect only the missing work.
The caller need not know an internal workflow ID. Select the operations that
serve the question; their real input dependencies, not a fixed catalog sequence,
determine execution order. Finishing a section does not stop the surrounding task.

## Through the Egbe connector

The bundled runners, adapters, publishers and resume journals need a set-up
project workspace: in a persistent project workspace not set up yet, call
`egbe_local_setup`; otherwise tell the founder which step needs it. Through the
connector alone, answer a narrow assignment with the capabilities they call:
`egbe-os-research` for cited narrative research, and `egbe-os-search`,
`egbe-os-scrape` or Google keyword ideas (`egbe-os-google-ads`) for
measurements. Keep the brief, requests, job IDs, raw responses and sources at
their `egbe-docs/research/<id>/` paths in Egbe's artifact store, as
`egbe-os-quickstart` → `references/artifact-sync.md` ("Through the Egbe
connector") describes. Label the result as collected without the section runner:
it has no runner receipt or completion review and is not a published PMR
section.

## Choose the operation

Find available sections and their contracts in
[references/catalog.v1.json](references/catalog.v1.json); read only the selected
workflows and [research artifact contract](references/contracts/research-artifacts.md).

- For provider-backed narrative research, use the section's bundled OS Research
  runner with `--assignment "bounded question and scope"` or
  `--assignment-file <existing-task-text>`. Its evidence prompt does not replace
  the task. The deterministic query preserves selected context, assignment and
  receipt-backed supporting evidence.
- For measurements (keywords, competitors, ad libraries, creative/funnel data,
  reviews, communities and comparable fleet results), use the corresponding
  bundled adapters. Their CLI inputs bound collection. Keep raw observations,
  dates, native scope, units, identity/relevance decisions and coverage separate
  from hypotheses about effectiveness.
- Geography Comparison applies the requested comparison to validated existing
  inputs, using its publisher. It has no code-owned country score and does not
  implicitly start other research.
- Organic Trend Watch uses its dedicated skill and the provider-safe context
  builder named by its workflow. Do not duplicate that runtime.
- [Local research](references/workflows/local-research.md) explains research IDs,
  resume and optional multi-section publication.
- [Preview](references/workflows/preview.md) and
  [recommendation serialization](references/workflows/recommendations.md) are
  available when that output is requested. A narrow investigation does not
  require the complete recommendation/preview package.

## Execution and handoff

Work from the prepared assignment; choose one stable `EGBE_RESEARCH_ID` and
preserve its execution state. Do not modify the PRD. Pass `--context-file` only
for deliberately selected provider-safe context needed beyond the assignment or
operation inputs. Supply its relevant contents, not local links an external
researcher cannot read. Do not sweep the repository, chat, profile, env or personal
notes into a request. The shared input snapshot retains what was used for resume;
only declared, validated upstream evidence is added by the operation.
The OS gateway, metered starts, cumulative limits, cache keys, timeout/retry
journals and source-specific access restrictions remain authoritative.

Preserve the actual request, response, raw evidence and receipt hashes. Reuse
a matching completed response or resume its known job. Changed task or prompt
inputs are not the same research question: the runner preserves the old work
and requires a separate research ID before a new paid submission. A skill
update alone never warrants a paid rerun; prior evidence remains usable for
what it actually investigated. Complete the bounded transport-truncation review
for OS Research responses; uncertainty never triggers an extra submission.

Follow the lifecycle/funnel contracts for authorized signup or form actions,
stable aliases, uncertain outcomes and privacy. No research assignment grants
additional authority to submit forms, launch campaigns or spend beyond scope.

Hand off the relevant findings, sources, coverage and unresolved questions from
the existing research artifacts. Their receipts remain evidence provenance, not
a requirement to produce a preview or a new product-definition input file.
Link findings into the caller's current requirements or plan; do not copy a new
master report between stages.

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-product-market-research/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-product-market-research/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-product-market-research/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `scripts/build-organic-trend-context.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/build-organic-trend-context.py | `057c0b55dbfbf733759f40d86a27c2c3e24e81b662b0b3f6296a74d232119090` |
| `scripts/build-preview-context.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/build-preview-context.py | `8e8bcc82170d74e15cc81186a76b7a4679ccb4ef67be8c03814235ef9fe2eefa` |
| `scripts/build-research-query.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/build-research-query.py | `32db9abbe7b2aada1304fd58a911c835e26c3ace1d7668e9bc43e66e88eddf45` |
| `scripts/channel-footprint-model.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/channel-footprint-model.py | `ac3ceb355a203d829658f446e4d189135142db9b130060eb6f4284936e6535f9` |
| `scripts/connection_identity.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/connection_identity.py | `32851ccf3431289e470cd83c5ec649515cafe374a589a38beae353e167e726b5` |
| `scripts/creative-model.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/creative-model.py | `f18b0b1ee07b8bde0e73581df2689f8fafae2b65ebf7fed665994b49c82be8ba` |
| `scripts/creative-selection.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/creative-selection.py | `957b294536ce0d545ef2cfeb62d06b7df7de5309377344c49db67eb2a28f32f6` |
| `scripts/creative-semantics.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/creative-semantics.py | `794c5deb69fb4e4080d66241cb6b0f1bd022a7531c715b0fb90ca1ce63bf36e7` |
| `scripts/creative-video.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/creative-video.py | `2d18c77614de38238179d8768c5294320c3c7b160d36651ceeed8747139c124d` |
| `scripts/egbe_artifacts.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/egbe_artifacts.py | `292df7b2d1b0863d9bed85d166ba66e6798ebc66b90ec0a3c89d018102ddbe3a` |
| `scripts/finalize-organic-trend-watch.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/finalize-organic-trend-watch.py | `7364ecc342a4dfabee9d4ba7156f24b67303a26865dbba80c8e1b6b8d667834a` |
| `scripts/funnel-email-review.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/funnel-email-review.py | `d075f27b50e2a19dd4af5d9cac0635de383ee5dab13423df05ee028d7149473a` |
| `scripts/funnel-model.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/funnel-model.py | `c6b2cd629ce44a8eace66e2624418f9d0c2921e78b74fd9213414d2dd40f6258` |
| `scripts/funnel_features.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/funnel_features.py | `19f09cf26155bb6e847b992cfb95a02e7acb3dfb75d36859d070cc7eef60a955` |
| `scripts/geography-comparison-contract.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/geography-comparison-contract.py | `edcf13b7a6e3a6ce983e57c315a7635b365ad8f8473c039069c585aaf48aaa30` |
| `scripts/geography-comparison.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/geography-comparison.py | `187e2133755a0806bce05347df8e4f11f3dfce63d00bb917f9773fd8308399f7` |
| `scripts/keyword-forecast.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/keyword-forecast.py | `dc2a628dbc1efed3140b00e102a2590d6ac78a6534feeacea961e0662a6a6fcc` |
| `scripts/keyword-locale-publication.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/keyword-locale-publication.py | `c79a0d2a1b9e476fdc6da94900146d2d5b8046403f5ffafa428bc844de119f86` |
| `scripts/lifecycle-start.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/lifecycle-start.py | `0d802309c1cdf712876d475d31e141796915a5e142ac951b620a7696e325ea76` |
| `scripts/persist-research-report.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/persist-research-report.py | `bac564afe806903a9ee7e60c6ab04ae76a4b4cbe47814177821d9d26618184be` |
| `scripts/research-artifact-io.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research-artifact-io.py | `e46571d81843ccccf1e334cbf332ee4a623bbf6d1099e5bd4505ca1ba76d58a8` |
| `scripts/research-evidence.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research-evidence.py | `3711c2764a797f25d584fb70b7f9698100023dbea5d8376c9ca9cfe211d77af3` |
| `scripts/research-policy.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research-policy.py | `a8759cc8c060018ff4883fb5bdce9087f13eed4a4e842cb7be2fa059d739d8a9` |
| `scripts/research-section-runtime.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research-section-runtime.py | `adee175ab857213535aa0bb5a238b23f056d9be1ed9964371e2bd876a14cafd8` |
| `scripts/research-section-workflow.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research-section-workflow.py | `ac2dc4518b4a3d69111ed6ed4021c8984f1294b7693873fdbb4e8e8742a3fcde` |
| `scripts/research_integrity.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/research_integrity.py | `9b871afc4757b2ab040466e8db91d5f8d28df19e1f6df055168d5b72b1e29ec9` |
| `scripts/review-research-completion.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/review-research-completion.py | `67d900dbb05083f3b69c309599894c2994dc215d80cacd3a080a76ddeca2770f` |
| `scripts/run-acquisition-channels.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-acquisition-channels.py | `461e5b5ad73b25190190a66a302e4385a93cf6c38e924626628725310833ff0e` |
| `scripts/run-channel-footprint.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-channel-footprint.py | `ad391c961c012b8d02d922b296ef974cdc8ba0f4f6d53396b13ec49634a11aed` |
| `scripts/run-community-demand.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-community-demand.py | `d55bb8562f1e36faf39b724809e103204dd23735b6a8d09d8a851c03817f1670` |
| `scripts/run-competitive-landscape.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-competitive-landscape.py | `a93d05331f2b7615aed44abc39761df59bab2ccfa379202368bc3e82c803cc3f` |
| `scripts/run-competitor-ads.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-competitor-ads.py | `2a0b4afc2e1e09b1670a464ccfa7f9a416b4296e803b1611d54a2b1a026ffce3` |
| `scripts/run-competitor-set.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-competitor-set.py | `0bbe162607e69d303657170cdece98cf2659c00b1aa02d83ae3a8a3bd3d4ccb1` |
| `scripts/run-creative-patterns.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-creative-patterns.py | `58fb7d07a425cf30ad230fffc521eea12eaf2d1eb07099cad06e410e80208429` |
| `scripts/run-demand-validation.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-demand-validation.py | `d6b26615946ad5686c2c1d02450af8af57ed18a213df7bcd703fbb2e14b240a2` |
| `scripts/run-fleet-prior.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-fleet-prior.py | `af02f5999a81047457546c847df09c406460a176d6cc453dc42b344ed3c83bff` |
| `scripts/run-funnel-teardown.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-funnel-teardown.py | `3e2f0dbc5699d2c0559b8e567b395de15cb6e0760f7e60994a0ed73d6948aec7` |
| `scripts/run-keyword-economics.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-keyword-economics.py | `d9553f3acf7ea439ca8fcd79d1978eb66cad2f8fa6cacf465a3bc25d1eb3311b` |
| `scripts/run-lifecycle-capture.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-lifecycle-capture.py | `f9f37e683f572a2e21d3150d60cea9523eb5b6e3ed4fe47704c5fbfb477f8fa2` |
| `scripts/run-market-size-and-dynamics.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-market-size-and-dynamics.py | `9d2275f67d9ca5078d7bf5d7c7e93a88ebdd97bafcb757ee753bace6d99c3fd7` |
| `scripts/run-os-research.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-os-research.py | `349b2162f33f83109caa695ed292b15adc87ab8385b5e306e5fc5c064a954b37` |
| `scripts/run-pricing-and-monetization.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-pricing-and-monetization.py | `31dfb71c258e7d9e74e45c12a352462bd81afa0476ae8d8e47cb5734be3c04cb` |
| `scripts/run-review-mining.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-review-mining.py | `61ce7f124a328ff91a5050862cd6c8b2a9fed1cc98e2a9451d7f4f57f1d8b4dd` |
| `scripts/run-target-audience.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-target-audience.py | `e920015c4399d61ea427a1cd2080b97b70f135ef4388cb65fd1d82208f8ccb46` |
| `scripts/run-unit-economics.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-unit-economics.py | `3af86ce4bb8c8926c8821ebd9e08b460c81128e926375fae8eb607e5bd6b9093` |
| `scripts/run-value-proposition.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/run-value-proposition.py | `a4711e9de27025bee881019e7d3f14fbc2afead0887d82013f7999f1aaee0c25` |
| `scripts/upsert-markdown-section.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/upsert-markdown-section.py | `2cfbe24385c7a085e0a1c50ca94418356cc6db3a85298d6dd9ff53c2c83eec76` |
| `scripts/walk-funnels.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/walk-funnels.py | `c7f4668ae0aaa5a0a4137ff0871bb5f2d3e44b381dbe686273e084a6fd584876` |
| `scripts/write-preview.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/write-preview.py | `f76ef20ceb660d5cf91111dd9f918ca3ed13e7ef7ad9addf488dffed0d343a41` |
| `scripts/write-recommendations.py` | https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/scripts/write-recommendations.py | `677329daccca8985c690ffb9b08e744192469f1edcd14beb40574e4cefb71763` |
