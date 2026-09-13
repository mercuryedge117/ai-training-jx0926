# Runbook: payment-service

**Owner:** Payments team (on-call rotation) · **Last updated:** 2026-07-15 (post inc-0713)

## Service overview
payment-service handles charge creation (`POST /v2/charges`), refunds, saved payment
methods, and webhook delivery to merchants. It talks to `payment-db` (PostgreSQL,
connection pool max 200) and the external card processor.

## Key dashboards & alerts
- Grafana: `payment-api` dashboard (p99 latency, 5xx rate, pool utilisation)
- SLO: p99 < 800ms, 5xx < 1%
- Alerts: pool utilisation warn at 70%, page at 90% (added after inc-0713)

## First 10 minutes checklist (any payment alert)
1. Check the `payment-api` dashboard: is it latency, errors, or both?
2. Check `payment-db` active connections. Pinned at 200/200 → pool exhaustion, go to the playbook below.
3. Check the deploy log — anything shipped in the last 2 hours is the prime suspect.
4. Declare severity in #incidents; SEV-2 if checkout is customer-visibly degraded.
5. Default action for deploy-correlated incidents: **roll back first, debug later.**

## Playbook: connection pool exhaustion
Symptoms: p99 spike + 5xx on /charges, `pg_stat_activity` full of idle-in-transaction
sessions from payment-service.

1. Identify the holding queries:
   `SELECT pid, state, query_start, left(query,60) FROM pg_stat_activity WHERE application_name='payment-service' AND state='idle in transaction';`
2. If correlated with a recent deploy → roll back that deploy.
3. If not deploy-correlated → check for traffic anomaly, then consider raising the pool cap as a stopgap (requires DBA approval).
4. After mitigation, confirm: pool < 50%, p99 < 800ms, 5xx < 1% for 15 consecutive minutes.

## Rollback procedure
`deployctl rollback payment-service --to <previous-tag>` — takes ~20 min to fully drain.
Verify pod versions with `kubectl get pods -l app=payment-service -o wide`.

## Charge safety guarantees
Charges are captured only after processor confirmation. A request that fails before
capture **cannot double-charge**; the order simply fails. Refund path is idempotent.
