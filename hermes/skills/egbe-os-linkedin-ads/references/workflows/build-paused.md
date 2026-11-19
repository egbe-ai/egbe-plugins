# Build without delivery and recover

Read artifacts and the API reference. Resolve recorded IDs through owned GETs.
If both formats are requested, create separate native campaigns under the same
product-owned group and keep the aggregate daily spend within authorization.

1. Read account/Page, pricing and targeting; save the intended build.
2. Create the group with product_slug and schedule. OS creates it DRAFT: LinkedIn
   does not allow initial PAUSED groups. A requested "paused build" uses DRAFT
   throughout; never activate parents merely to make child creation possible.
3. Create each campaign with group ID, format, targeting, locale, daily USD budget,
   CPC and schedule. OS creates it DRAFT; LinkedIn rejects PAUSED campaigns
   beneath a DRAFT group.
4. Upload each approved PNG/JPEG via `POST /ads/linkedin/images`. Poll its owned
   GET until `status=AVAILABLE`; processing is asynchronous. Do not create a
   new upload merely because processing is slow.
5. Create a creative with campaign ID, owned image URN, approved copy and exact
   destination. Single Image creates Direct Sponsored Content with
   `feedDistribution=NONE`; it does not publish to the organic Page feed.
   Text Ad uses its separate native content payload. Both creatives start DRAFT.
6. Read back every object and parent binding; record moderation/serving reasons,
   DRAFT states, image availability, budget and destination. Existing PAUSED
   objects are also non-serving; preserve them when resuming work. For Single
   Image the creative may read back a content reference instead of inline content;
   the owned `/creatives/{id}/content` GET resolves that post for review.
7. Save state, readback and operation outcomes; return the specific remaining
   blockers. A non-serving build does not prove delivery. Creative review starts
   on activation; absent review on a DRAFT creative is expected, not a reason
   to activate it or wait for moderation during this build.

Uncertain create returns 409 with recovery instructions. Retry the same key/body.
If the response still requires Egbe team reconciliation, stop creation and
preserve the key: the gateway will not silently create another resource.
After an update timeout, retry the same operation for verified readback; a newer
mutation supersedes earlier update keys, so an old launch cannot undo a pause.

For Text Ads, use the bounded creative PATCH to change copy/image/destination;
it merges changed fields into fresh readback and preserves status. For Single
Image content changes, prepare an explicitly authorized new
DRAFT creative under the existing campaign, inspect it, then perform the approved
switch and pause the old creative. Do not delete history or recreate the campaign.
Creative internal names can be changed in place for both formats. If LinkedIn
rejects a field for the current creative state, report that reason; do not silently
replace the creative or change its delivery status.
