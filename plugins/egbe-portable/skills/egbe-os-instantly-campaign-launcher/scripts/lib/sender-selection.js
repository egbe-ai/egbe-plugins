// Which mailboxes a campaign sends from. The Instantly workspace behind OS is
// shared by every business, so a run names its own senders: campaign.email_list
// (exact addresses) or campaign.sender_domains (the active mailboxes on those
// domains). A run that names neither would send one business's emails from
// another business's mailboxes, so the launch stops instead.

function normalizeEmail(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function domainOf(email) {
  const at = email.lastIndexOf("@");
  return at >= 0 ? email.slice(at + 1) : "";
}

function isActive(acc) {
  return acc.status === 1 && (acc.daily_limit == null || acc.daily_limit > 0);
}

function toSender(acc) {
  return {
    email: normalizeEmail(acc.email),
    first_name: acc.first_name,
    last_name: acc.last_name,
    daily_limit: acc.daily_limit,
  };
}

function listOf(value) {
  return Array.isArray(value) ? value : [];
}

// Returns { senders } or { error }. `accounts` is every mailbox in the
// workspace (any status), as GET /accounts returns them.
function selectSenders(campaign, accounts) {
  const emailList = listOf(campaign?.email_list)
    .map(normalizeEmail)
    .filter(Boolean);
  const domains = listOf(campaign?.sender_domains)
    .map((d) => normalizeEmail(d).replace(/^@/, ""))
    .filter(Boolean);

  if (!emailList.length && !domains.length) {
    return {
      error:
        "Set campaign.email_list or campaign.sender_domains in the run spec. The Instantly " +
        "workspace is shared between businesses; the launcher no longer picks mailboxes " +
        "from it on its own.",
    };
  }
  if (emailList.length && domains.length) {
    return {
      error: "Set only one of campaign.email_list and campaign.sender_domains.",
    };
  }

  const byEmail = new Map();
  for (const acc of accounts) {
    const email = normalizeEmail(acc.email);
    if (email) byEmail.set(email, acc);
  }

  if (emailList.length) {
    const missing = emailList.filter((e) => !byEmail.has(e));
    if (missing.length) {
      return {
        error: `Not in the Instantly workspace: ${missing.join(", ")}.`,
      };
    }
    const inactive = emailList.filter((e) => !isActive(byEmail.get(e)));
    if (inactive.length) {
      return {
        error:
          `Paused or daily limit 0: ${inactive.join(", ")}. Fix them in Instantly ` +
          "or remove them from campaign.email_list.",
      };
    }
    return {
      senders: [...new Set(emailList)].map((e) => toSender(byEmail.get(e))),
    };
  }

  const onDomains = [...byEmail.values()]
    .filter(
      (acc) =>
        domains.includes(domainOf(normalizeEmail(acc.email))) && isActive(acc),
    )
    .sort((a, b) =>
      normalizeEmail(a.email).localeCompare(normalizeEmail(b.email)),
    );
  if (!onDomains.length) {
    return {
      error: `No active mailboxes on ${domains.join(", ")} in the Instantly workspace.`,
    };
  }
  const max = Math.max(
    1,
    Number(campaign?.max_sending_accounts) || onDomains.length,
  );
  return { senders: onDomains.slice(0, max).map(toSender) };
}

module.exports = { selectSenders };
