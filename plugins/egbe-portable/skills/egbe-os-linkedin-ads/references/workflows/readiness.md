# Readiness

Call `GET /ads/linkedin/readiness` and `GET /ads/linkedin/account`.
Record account ID, USD currency, linked organization URN, status, serving holds
and timestamp in channel-readiness. Check the Page is the intended advertiser.
A successful account GET verifies read access only. `ready:null` means remaining
permissions/serving checks are unverified, not a green light to spend.

The Egbe team supplies a verified/approved LinkedIn developer app, an enabled USD
Campaign Manager account with billing, and member OAuth access. The member needs
the appropriate account management role and Page role for Direct Sponsored Content.
Client ID/secret alone cannot manage campaigns: LinkedIn Marketing uses member
authorization, not client-credentials OAuth. Development access may require the
selected account on the app's allowlist.

If access is missing, return the precise failing operation/status and required
action from the Egbe team. Do not create disposable campaigns merely to probe permissions.
The requested non-serving DRAFT build is the controlled write test; report which steps
succeeded and which permissions remain unverified.

## Egbe admin configuration (not product credentials)

Tools deployment reads:
- `LINKEDIN_ADS_CLIENT_ID`, `LINKEDIN_ADS_CLIENT_SECRET`;
- `LINKEDIN_ADS_ACCESS_TOKEN`, `LINKEDIN_ADS_ACCESS_TOKEN_EXPIRES_AT`;
- optional `LINKEDIN_ADS_REFRESH_TOKEN`, `LINKEDIN_ADS_REFRESH_TOKEN_EXPIRES_AT`;
- `LINKEDIN_ADS_ACCOUNT_ID`, `LINKEDIN_ADS_REDIRECT_URI`;
- `LINKEDIN_ADS_API_VERSION` (YYYYMM, currently 202608).

Expiry values are Unix seconds. Blank refresh fields are legitimate: programmatic
refresh is available only when LinkedIn grants it. Without refresh, the Egbe team
must renew member consent before access expires. Gateway refreshes near expiry
when a valid refresh token is configured; it does not rotate the configured
refresh token or write secrets back to the repository.

Register the exact redirect URI in the LinkedIn app. OAuth setup by an Egbe admin:
1. Open `https://www.linkedin.com/oauth/v2/authorization` with URL-encoded
   `response_type=code`, `client_id`, `redirect_uri`, random `state` and the
   app-approved scopes (`rw_ads`, `r_ads`, `r_ads_reporting`; applicable organization
   social permissions for image/DSC operations).
2. The authorized member signs in and consents; verify returned state locally.
3. Exchange the one-time code server-side at
   `https://www.linkedin.com/oauth/v2/accessToken` with form fields
   `grant_type=authorization_code`, code, identical redirect_uri, client_id,
   client_secret. Save returned tokens/expiry only in Egbe's restricted secret storage.
4. Configure the account ID from Campaign Manager; the gateway discovers its Page
   through account `reference`. Do not put Page identity into product source.

Exact permissions depend on the approved API products:
[Marketing authentication](https://learn.microsoft.com/en-us/linkedin/marketing/getting-started),
[authorization code flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow),
[refresh tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).

Optional conversion measurement additionally needs approved Conversions API
access and member scopes `rw_conversions`, `r_ads`. Successful rule reads do
not prove create/event-ingestion permission. Check through the requested
configuration and real events, not a throwaway conversion.

Advertising, Conversions and any future Ad Library product have independent
approval/version lifecycles. Current gateway calls are pinned to 202608; recheck
the relevant API product when changing the version, not every routine campaign.
`BILLING_HOLD` blocks serving, not necessarily DRAFT object creation; don't
change billing or launch to test this assumption. Record the provider's response.
