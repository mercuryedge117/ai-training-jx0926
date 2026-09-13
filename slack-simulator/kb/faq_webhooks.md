# FAQ: Webhooks

## Are webhook payloads signed?
Yes. Every webhook is signed with **HMAC-SHA256** using your webhook secret (found in
Dashboard → Developers → Webhooks). The signature is sent in the
`X-CloudCart-Signature` header:

```
X-CloudCart-Signature: t=1720900000,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

Verify by computing `HMAC-SHA256(secret, t + "." + raw_body)` and comparing to `v1`
with a constant-time comparison. Reject if the timestamp is older than 5 minutes
(replay protection).

## Are webhook deliveries retried?
Yes — failed deliveries (non-2xx or >10s timeout) are retried with exponential backoff
for up to 24 hours. Each delivery attempt carries a unique `X-CloudCart-Delivery-Id`
header; deduplicate on it, since a slow-but-successful delivery plus a retry can
result in the same event arriving twice.

## Which events are available?
`charge.succeeded`, `charge.failed`, `refund.created`, `payout.paid`,
`payment_method.attached`, `dispute.opened`. Subscribe per-endpoint in the dashboard.

## Can I replay a webhook?
Yes — Dashboard → Developers → Webhooks → Event log → "Resend". Resent events keep
their original event id but get a new delivery id.
