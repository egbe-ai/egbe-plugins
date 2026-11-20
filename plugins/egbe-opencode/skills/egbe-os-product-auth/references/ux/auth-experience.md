# Authentication Experience

## Shared Navigation

Authentication changes the existing shared navigation instead of adding a
second header.

Signed out:

- keep the primary product/first-value CTA;
- show a clear login action;
- do not force signup before first value when the product supports public
  activation.

Signed in:

- replace guest login/signup controls with a recognizable user-menu trigger;
- show a non-sensitive identity such as name or email;
- provide one clear action to continue into the existing protected experience;
- provide logout;
- keep the menu keyboard accessible and usable in the mobile navigation.

## Forms

- Present the selected methods with the accepted hierarchy; use a clear semantic
  separator when more than one method is offered. Do not add an unselected
  method to fill a form or layout.
- Match the email method: show exactly email and password for the password
  profile, or exactly email for passwordless email.
- Do not ask for name, company, username, password confirmation, or other
  profile data before the account exists; use email as the initial identity.
- Use persistent visible labels and correct profile-appropriate autocomplete
  values.
- Explain the product benefit or continuation, not internal auth mechanics.
- Cross-link signup and login.
- Show password requirements before submission only when passwords are used.
- Disable repeat submission while pending and preserve entered email on errors.
- Move focus to a concise visible error without revealing account existence.
- Provide password visibility controls with an accessible name when useful.

## Continuity

After signup/login, send the user to the intended useful route. If a public
first-value result led to signup, explain what will be saved or continued and
restore that exact result after authentication.

Do not redirect to an empty page, a missing route, the auth page itself, or
localhost. If the accepted destination is not implemented, a minimal protected
verification surface may show current-user identity and logout. It proves only
the auth mechanism, not the completed product journey; do not invent a dashboard
or placeholder feature controls to stand in for the missing destination.

## Recovery And Verification

Show recovery or verification UI only when the server flow and mail delivery
actually work. Never ship dead "Forgot password" or "Resend" controls. Follow
the account-recovery workflow for password recovery or separate verification,
and the passwordless-email workflow for email sign-in links.
