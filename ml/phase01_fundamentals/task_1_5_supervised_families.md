# Task 1.5 — Supervised learning families

These are the four families we will keep straight for the rest of the plan. None of this uses recommendation-service tables yet; it only names where they will land.

| Family | One sentence | Maps to our project |
| --- | --- | --- |
| **Classification** | Predict a discrete class, e.g. click vs no-click. | Future click model: `P(user clicks item \| features)`. |
| **Regression** | Predict a number. | Candidate `score` in Postgres is already a number; a model could *learn* a score instead of using the catalog value. |
| **Ranking** | Put a list in a useful order (top-K), not just score one pair. | `GET /recommendations` returns an ordered list of 5 item ids. |
| **Unsupervised** | Find structure with no labels (e.g. k-means clusters). | Grouping users by behavior without a click label — not how v1/v2 work, and not Phase 3. |

v1/v2 today are **none of the trained families**: they are handwritten ranking rules with no `.fit()`.
