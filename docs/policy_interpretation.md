# Policy Interpretation Notes

This document records how the repository policy is operationalized by the adjudication layer.

## Covered categories

The platform routes claims into a small set of deterministic coverage buckets:

- medical cancellation / rescheduling
- legal-obligation cancellation
- theft / criminal-incident cancellation
- personal effects
- missed departure / missed connection
- not covered

## Required proof philosophy

The policy layer is intentionally stricter than simple keyword matching. Coverage requires both:

1. a covered reason, and
2. sufficiently trustworthy supporting evidence.

Examples:

- medical claims require medical evidence that actually supports incapacity or a covered medical event
- theft-related claims require police-style or equivalent incident evidence
- legal-obligation claims require summons-style documentation
- missed-departure claims require incident context plus booking proof

## Signal separation

The routing layer uses four explicit signal groups:

- **support**
- **contradiction**
- **hard invalidity**
- **soft uncertainty**

This keeps document verification and final decisioning auditable and makes it easier to inspect why a claim resolved to `APPROVE`, `DENY`, or `UNCERTAIN`.
