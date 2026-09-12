# Task 4.5 — Content-based gap

Invented item categories (not in the database):

| item_id | fake category |
| --- | --- |
| 10, 20, 30 | electronics |
| 40, 50, 60 | home |
| 70, 80, 90, 91, 94 | media |

True content-based filtering matches item *attributes* to a user profile (categories I clicked, text, price band). v2 cannot do that today: `recommendation_items` only has `item_id`, `score`, `is_active`. There is no category or text column, and `UserFeatures` has no category histogram. Last-item boosting is identity matching (`item_id == last_item_id`), not content. **Do not add a DB column in this phase** — the gap is documented so we do not pretend v2 is content-based.
