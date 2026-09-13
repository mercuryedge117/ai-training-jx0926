# Incident Response Policy

## Severity levels
- **SEV-1:** Full outage of checkout or data loss. Page everyone, exec notification.
- **SEV-2:** Customer-visible degradation (e.g. elevated checkout failures). War room in #incidents, EM is incident commander.
- **SEV-3:** Internal-only impact or single-customer issue with workaround.

## Roles
- **Incident Commander (IC):** runs the war room, makes rollback/mitigation calls, owns comms cadence. Default: EM on duty.
- **Investigation Lead:** senior engineer driving root-cause work.
- **Mitigation:** on-call infra engineer, executes rollbacks/scaling.
- **Comms:** support engineer; no customer communication before IC confirms impact scope.

## Rules of engagement
1. Roll back first, debug later, when an incident correlates with a recent deploy.
2. All discussion in the #incidents war-room thread — no side DMs for decisions.
3. Status page updated within 30 minutes of SEV-1/SEV-2 confirmation.
4. Blameless postmortem within 3 business days; action items must have an owner and a due date.

## Customer communication templates
- **Investigating:** "We are investigating elevated errors affecting checkout. Updates every 30 minutes."
- **Resolved:** "The issue was resolved at <time UTC>. Root cause: <one line>. No double charges occurred; failed orders were not processed."
