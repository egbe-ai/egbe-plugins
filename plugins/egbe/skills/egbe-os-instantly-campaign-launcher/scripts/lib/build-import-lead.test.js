#!/usr/bin/env node
// Runtime tests for buildImportLead — the /leads/add payload shape.
// Non-standard lead fields must survive the import as personalization /
// custom_variables instead of being dropped silently.
//
// Run: node scripts/lib/build-import-lead.test.js

const { buildImportLead } = require("./helpers");

let failed = 0;
function check(name, cond, ...detail) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`, ...detail);
    failed += 1;
  }
}

const base = buildImportLead({
  email: "jane@acme.com",
  firstName: "Jane",
  last_name: "Doe",
  companyName: "Acme",
  website: "https://acme.com",
});
check(
  "standard fields map to snake_case import shape",
  base.email === "jane@acme.com" &&
    base.first_name === "Jane" &&
    base.last_name === "Doe" &&
    base.company_name === "Acme" &&
    base.website === "https://acme.com",
  base,
);
check(
  "no personalization/custom_variables keys when absent",
  !("personalization" in base) && !("custom_variables" in base),
  base,
);

const rich = buildImportLead({
  email: "jane@acme.com",
  first_name: "Jane",
  personalization: "Saw your before/after gallery from the Lakeview listing",
  city: "Austin",
  listing_count: 12,
  uses_wix: true,
  _internal: { skip: true },
});
check(
  "personalization passes through as a first-class field",
  rich.personalization ===
    "Saw your before/after gallery from the Lakeview listing",
  rich,
);
check(
  "extra scalar fields become custom_variables",
  rich.custom_variables?.city === "Austin" &&
    rich.custom_variables?.listing_count === 12,
  rich,
);
check(
  "boolean custom values are retained",
  rich.custom_variables?.uses_wix === true,
  rich,
);
check(
  "non-scalar fields are not forwarded",
  !("_internal" in (rich.custom_variables || {})),
  rich,
);

const native = buildImportLead({
  email: "jane@acme.com",
  phone: "+1 512 555 0100",
  job_title: "Owner",
  lt_interest_status: 1,
  city: "Austin",
});
check(
  "supported native fields stay native, not demoted to custom_variables",
  native.phone === "+1 512 555 0100" &&
    native.job_title === "Owner" &&
    native.lt_interest_status === 1 &&
    !("phone" in (native.custom_variables || {})) &&
    !("job_title" in (native.custom_variables || {})) &&
    native.custom_variables?.city === "Austin",
  native,
);
const nativeRoundTrip = buildImportLead(native);
check(
  "native fields survive the carry-over round-trip",
  nativeRoundTrip.phone === "+1 512 555 0100" &&
    nativeRoundTrip.job_title === "Owner" &&
    nativeRoundTrip.custom_variables?.city === "Austin",
  nativeRoundTrip,
);

const blankPersonalization = buildImportLead({
  email: "a@b.c",
  personalization: "   ",
});
check(
  "whitespace-only personalization is dropped",
  !("personalization" in blankPersonalization),
  blankPersonalization,
);

// Carry-over leads round-trip through buildImportLead (launch stores its
// output, replenish re-applies it) — a second pass must not drop anything.
const roundTrip = buildImportLead(rich);
check(
  "idempotent: custom_variables survive a second pass (carry-over path)",
  roundTrip.custom_variables?.city === "Austin" &&
    roundTrip.custom_variables?.listing_count === 12 &&
    roundTrip.custom_variables?.uses_wix === true &&
    roundTrip.personalization === rich.personalization,
  roundTrip,
);

const oversize = buildImportLead({
  email: "a@b.c",
  scraped_blob: "x".repeat(5000),
});
check(
  "oversized custom values are dropped (scraped-blob guard)",
  !("custom_variables" in oversize),
  oversize,
);

// Launcher-only preflight overrides must not reach Instantly as custom
// variables (a boolean would otherwise pass the scalar filter).
const confirmed = buildImportLead({
  email: "li@acme.com",
  first_name: "Li",
  first_name_confirmed: true,
  company_name: "KPMG LLP",
  company_name_confirmed: true,
  city: "Dubai",
});
check(
  "first_name_confirmed / company_name_confirmed are not forwarded",
  confirmed.first_name === "Li" &&
    !("first_name_confirmed" in confirmed) &&
    !("first_name_confirmed" in (confirmed.custom_variables || {})) &&
    !("company_name_confirmed" in (confirmed.custom_variables || {})) &&
    confirmed.custom_variables?.city === "Dubai",
  confirmed,
);

if (failed > 0) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll build-import-lead checks passed");
