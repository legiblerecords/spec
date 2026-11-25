# Data taxonomy notice

Data categories, uses and subjects from Fideslang 3.1.4 by Ethyca (https://github.com/ethyca/fideslang), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changed by Monorail: added entries are marked `source: monorail`.

Monorail's additions and its default classification are licensed under CC BY 4.0 as well, so the whole of `v1.json` is.

The licence text is at https://creativecommons.org/licenses/by/4.0/legalcode and in `LICENSE`. `v1.json` is written by `scripts/sync-taxonomy.mjs` from Track's taxonomy, which is generated from the Fideslang files as published; `SOURCE` says which commit.

## Changes by Monorail

Fideslang's rows are otherwise unchanged. Monorail changed:

- Added 45 categories, marked `source: monorail`:
  - `company`
  - `company.engineering`
  - `company.engineering.design`
  - `company.engineering.source_code`
  - `company.finance`
  - `company.finance.reports`
  - `company.finance.transactions`
  - `company.legal`
  - `company.legal.contracts`
  - `company.legal.privileged`
  - `company.legal.regulatory`
  - `company.operations`
  - `company.operations.internal_docs`
  - `company.operations.vendors`
  - `company.public`
  - `company.sales`
  - `company.sales.bookings`
  - `company.sales.customers`
  - `company.sales.marketing`
  - `company.sales.pipeline`
  - `company.sales.pricing`
  - `company.security`
  - `company.security.access`
  - `company.security.architecture`
  - `company.security.assessments`
  - `company.security.audit_reports`
  - `company.security.findings`
  - `company.security.findings.pentest`
  - `company.security.findings.scanner`
  - `company.security.findings.triaged`
  - `company.security.incidents`
  - `company.security.inventory`
  - `company.security.monitoring`
  - `company.security.program`
  - `company.strategy`
  - `unknown`
  - `user.contact.email.personal`
  - `user.contact.email.work`
  - `user.contact.phone_number.personal`
  - `user.contact.phone_number.work`
  - `user.content.files`
  - `user.content.messages`
  - `user.demographic.trade_union`
  - `user.workplace.disciplinary`
  - `user.workplace.performance`
- Added the subject `customer_user`.
- Marked the subjects `employee`, `consultant`, `customer`, `customer_user`, `prospect`, `supplier_vendor` and `job_applicant` as `common`.
- Added Monorail's default classification: a level and the reason for it on every category, regime tags, a floor on every subject, and the definitions of the levels and regimes.
