// Adding leads is not repeated on a 5xx, because the batch may have landed
// anyway; before the next add, leave out leads already in the campaign.

// Unknown or incomplete reads cannot establish that a previous import did
// not land. Stop before writing instead of relying on provider deduplication.
function leadsNotInCampaign(leads, present) {
  if (!present?.ok || !(present.emails instanceof Set)) {
    throw new Error(
      "Campaign lead list unavailable or incomplete; import stopped to avoid duplicate leads. " +
        "Restore the lead read surface and re-run; do not resend an uncertain batch manually.",
    );
  }
  return leads.filter(
    (lead) =>
      !present.emails.has(
        String(lead.email || "")
          .trim()
          .toLowerCase(),
      ),
  );
}

module.exports = { leadsNotInCampaign };
