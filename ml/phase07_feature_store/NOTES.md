# Phase 7 — recorded experiments

## Task 7.4 skew

Same temporal split as Phase 6. Honest model trained on point-in-time features.
Leaked model trained on each user's **final** Redis-like state (all events,
including the future), then scored on honest PIT test rows.

| | log_loss | ROC-AUC |
| --- | --- | --- |
| Honest PIT → PIT test | 1.065 | **0.560** |
| Leaked “Redis now” → PIT test | 1.020 | **0.280** |

Log loss can look similar on 10 rows. **ROC-AUC collapses** when the serving
features no longer contain the future the leaked model memorized. That is
training-serving skew.

## Task 7.3 fixture

User `123` first click: `click_count_before=0`. After replaying *all* of that
user’s events, `click_count` is larger. The two disagree.

## Exercises

1. `view` updates only `last_item_id` (verified).
2. Production uses one Kafka consumer group for history then Redis; a textbook
   store might split those jobs — documented in `NOTES_two_paths.md`.
3. Changing Redis JSON keys without changing training names is schema skew
   (`feature_schema_version` mismatch raises).
