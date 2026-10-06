# Input Data Provenance and Distribution Policy

**Scope:** the single raw input file that the whole pipeline reproduces from —
`data/raw/telco_churn_raw.csv`.
**Recorded:** 2026-10-05 (Phase 2, audit item FGA-07).
**Status:** file identity is fully recorded and machine-checked. **Redistribution
rights are NOT confirmed** — see [Distribution policy](#distribution-policy) for
the decision that was taken anyway, and for what would reverse it.

---

## 1. The file as tracked

| Property | Value |
|---|---|
| Path | `data/raw/telco_churn_raw.csv` |
| Tracked in Git | **Yes**, mode `100644`, blob `394eabead4b63e370b9582330fde1741552db1ee` |
| Size | 1,736,765 bytes |
| Lines | 7,044 (1 header + 7,043 data rows) |
| Columns | 33 (`CustomerID` … `Churn Reason`) |
| SHA-256 | `e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34` |
| MD5 | `508d1ee08d14df7ca10c7d9914608cb3` |
| Line endings | LF only (no CR bytes) |
| Encoding | ASCII/UTF-8, comma-delimited, header row present |
| Read by | `etl/inspect_raw_data.py::load_data()` with `dtype={"Zip Code": str}` (leading-zero protection), consumed by `etl/load_to_db.py` |

Verify the checksum yourself (from the repo root):

```bash
sha256sum data/raw/telco_churn_raw.csv
# expect e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34

# or, machine-checked:
echo "e984530b5b1c67a0f2abe6496e65b99ab8d163d7e1b4c83fc1c3e2d71db57a34  data/raw/telco_churn_raw.csv" | sha256sum -c -
```

`tests/test_reproducibility.py::TestInputProvenance` performs this check (and the
row/column/header checks) on every test run, and fails if the tracked file ever
changes without this document being updated.

### Column order as tracked

```text
CustomerID, Count, Country, State, City, Zip Code, Lat Long, Latitude, Longitude,
Gender, Senior Citizen, Partner, Dependents, Tenure Months, Phone Service,
Multiple Lines, Internet Service, Online Security, Online Backup, Device Protection,
Tech Support, Streaming TV, Streaming Movies, Contract, Paperless Billing,
Payment Method, Monthly Charges, Total Charges, Churn Label, Churn Value,
Churn Score, CLTV, Churn Reason
```

`Churn Score`, `CLTV` and `Churn Reason` are outcome-derived and are excluded from
model features by `training/preprocessing.py` (the leakage correction described in
`README.md` and `dashboard/business_report.md`). `Count` is constant and dropped
during cleaning.

---

## 2. Where it came from

| Property | Value |
|---|---|
| Dataset title | "Telco customer churn: IBM dataset" |
| Listing | <https://www.kaggle.com/datasets/yeanzc/telco-customer-churn-ibm-dataset> (linked from `README.md`) |
| Publisher / listing author | TanKY (`yeanzc`) |
| Listing alternate name | "IBM Cognos Analytics 11.1.3+ base samples dataset" |
| Listing version | Version 1 (single version; listing shows "Updated 6 years ago", i.e. ~2020) |
| File served by Kaggle | `Telco_customer_churn.xlsx` (1.37 MB), 7,043 observations × 33 variables |
| Stated licence on the listing | **"Other (specified in description)"** |
| Stated update frequency | Annually (listing has never been re-versioned) |
| Upstream (per the listing description) | IBM Cognos Analytics 11.1.3+ base samples; IBM Community blog `steven-macko/2019-07-11/telco-customer-churn-1113`; IBM Community "accelerators" catalogue |
| Nature of the data | **Fictional/synthetic** telco customers (7,043 California customers, Q3 snapshot) published by IBM as a product sample. No real personal data. |

### Two provenance gaps, stated plainly

1. **The tracked CSV is a conversion, not the downloaded file.** Kaggle serves an
   `.xlsx` workbook; this repository tracks a `.csv`. No conversion script, export
   setting or intermediate file is committed, so the tracked bytes cannot be
   regenerated from the Kaggle download by a documented step. The SHA-256 above
   therefore identifies *this repository's copy*, not a canonical upstream file.
2. **The cited upstream source page is gone.** The IBM Community blog post that the
   Kaggle listing names as its source returned **HTTP 404 "Page Not Found"** when
   checked on 2026-10-05, so IBM's own terms for the base-sample data could not be
   read at the place the listing points to.

Because of (1), "download it again from Kaggle and compare hashes" is not a
available verification path for this file. The checksum check verifies that a
reviewer's clone is the same input the recorded results were produced from — which
is the reproducibility property that actually matters here.

---

## 3. Distribution policy

### What could be established

- The Kaggle listing's licence is the catch-all **"Other (specified in
  description)"**, and the description contains **no redistribution grant** — it
  describes the columns and points at IBM Community pages.
- Mirrors of the same IBM Telco data on Kaggle declare **mutually incompatible**
  terms (Apache-2.0; CC BY-NC-SA 4.0; CC BY-NC-ND; "Data files © Original
  Authors"). Third-party GitHub copies apply their own code licences (MIT,
  Apache-2.0) to their *code* while attributing the data to Kaggle/IBM.
- IBM ships this data as a **product sample** for Cognos Analytics. Sample-data
  terms of that kind normally permit use and learning with the product; a clear
  public-redistribution grant for a derivative CSV in an unrelated public
  repository **could not be found**.

**Conclusion: redistribution permission is unconfirmed.** Nothing in this document
should be read as a claim that publishing the file is licensed. No blanket code
`LICENSE` has been added to this repository either, for the same reason (audit item
FGA-07, and the team-authorship question).

### The decision taken (repository owner, 2026-10-05)

**Keep the file tracked, and document its status honestly rather than pretend the
question is settled.** Reasons, in order of weight:

1. **Untracking would not unpublish it.** The file has been in this repository's
   public Git history since the original team sprint. Removing it at `HEAD` leaves
   every historical commit intact; actually withdrawing it would require a history
   rewrite, which the audit explicitly places out of scope.
2. **There is no credential-free acquisition path to document instead.** Kaggle
   requires a logged-in account to download, and the IBM Community page the listing
   cites is a 404. Untracking would therefore replace "clone and run" with
   "register on a third-party site, download a workbook, convert it to CSV by
   undocumented means, and hope your bytes match" — a strictly worse reproduction
   path for a reviewer, in exchange for no real reduction in exposure.
3. **The data is fictional IBM product-sample data**, not personal or
   commercially sensitive data, and it is the input every published result in this
   repository is derived from.

The `.gitignore` and `STRUCTURE.md` claims that the file was "gitignored" were
**false** and have been corrected as part of this phase (the ignore rules now
exclude everything in `data/raw/` *except* this one tracked input).

### What would reverse this decision

If the repository owner (or the original team/mentor) establishes that IBM's terms
do not permit redistribution, the withdrawal path is:

```bash
git rm --cached data/raw/telco_churn_raw.csv     # keep the local copy, stop tracking
# .gitignore already ignores data/raw/* — no rule change needed
# then: document the Kaggle acquisition + xlsx->CSV conversion + expected SHA-256
#       in this file, and give CI/tests a small permitted fixture instead
#       (audit FGA-07 / plan Phase 4). Note that history still contains the file.
```

Until then, treat the tracked copy as **retained under an unconfirmed-rights
decision that is recorded here on purpose**, not as cleared data.

---

## 4. Related records

- Environment, commands, timings and results for the pinned reproduction run:
  [`docs/reproduction_record.md`](reproduction_record.md)
- Historical (legacy) model comparison: [`evaluation/legacy/`](../evaluation/legacy/)
- Pinned rerun of the same legacy protocol:
  [`evaluation/reproduction/2026-10-05-pinned-single-split/`](../evaluation/reproduction/2026-10-05-pinned-single-split/)
- Column semantics and engineered features: [`docs/data_dictionary.md`](data_dictionary.md)
