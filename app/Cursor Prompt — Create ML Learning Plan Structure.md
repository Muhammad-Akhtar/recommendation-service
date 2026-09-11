You are working inside my existing `recommendation-service` project.

I have already implemented the production-oriented recommendation microservice. I now want to learn and implement the **actual AI/ML concepts that were only lightly covered or skipped**.

There is an existing file:

`ML_Implementation_Plan.md`

First, thoroughly analyze that file and the existing project structure/code before making any changes.

Also use the existing recommendation-service implementation as context. Do NOT replace the architecture that already exists.

## Existing architecture that must be respected

The existing recommendation system already has:

* FastAPI
* Pydantic
* PostgreSQL
* Redis
* Kafka
* Avro + Schema Registry
* Feature store
* Candidate catalog
* RecommendationService
* `model.py`
* `model_registry.py`
* Model v1/v2
* Prediction logging
* CTR monitoring
* Offline drift helpers
* Prometheus metrics
* OpenTelemetry
* Kubernetes
* Model/service version separation
* Canary deployment
* HPA
* Graceful degradation
* Circuit breaker
* Retry/backoff
* Kafka DLQ

The current model implementation is intentionally simple:

* v1 ranks candidates using popularity/score.
* v2 uses a manually defined scoring formula involving `click_count`, `purchase_count`, and `last_item_id`.
* `RecommendationService` loads features and candidates.
* The model only receives data and ranks candidates.
* The model must NOT directly access Redis, PostgreSQL, Kafka, HTTP, or other infrastructure.

This architecture is important because the purpose of this new work is to gradually replace/extend the simple ranking logic with genuine ML models while preserving the clean model boundary.

---

# PRIMARY OBJECTIVE

Create a **multi-file ML learning and implementation plan** that we can execute step-by-step over multiple Cursor context windows.

Do NOT put everything into one enormous plan file.

The plan must be divided into sequential phases, with each phase having its own Markdown file.

The files must reference each other so that if a new Cursor context window starts, Cursor can read the index and determine exactly:

1. What has already been completed
2. What phase comes next
3. What previous phase established
4. Which files/code it depends on
5. What concepts have already been learned
6. What concepts still need to be learned
7. What implementation should happen next

---

# REQUIRED DOCUMENT STRUCTURE

Create this documentation structure:

```text
docs/
└── ml/
    ├── 00_ML_PLAN_INDEX.md
    ├── 01_ML_FUNDAMENTALS.md
    ├── 02_DATA_AND_FEATURE_ENGINEERING.md
    ├── 03_FIRST_CLASSICAL_ML_MODEL.md
    ├── 04_RECOMMENDATION_SYSTEMS.md
    ├── 05_RANKING_AND_EVALUATION.md
    ├── 06_TRAINING_SERVING_PIPELINE.md
    ├── 07_FEATURE_STORE_AND_SERVING.md
    ├── 08_MODEL_EXPERIMENTATION.md
    ├── 09_MODEL_VERSIONING_AND_DEPLOYMENT.md
    ├── 10_ML_MONITORING_AND_DRIFT.md
    ├── 11_PROGRESSIVE_MODEL_IMPROVEMENT.md
    ├── 12_ADVANCED_RECOMMENDATION_SYSTEMS.md
    └── ML_CONTEXT.md
```

If the project already has a better documentation directory, inspect it first and choose a sensible location, but preserve the numbered structure.

---

# 00_ML_PLAN_INDEX.md

This is the most important file.

It must act as the **entry point for every future Cursor context window**.

Include:

## Project objective

Explain that the objective is to take the existing rule-based recommendation model and progressively learn/implement genuine ML while preserving the production architecture.

## Current state

Explicitly document:

* what is already implemented
* what ML concepts are already present
* what is only partially implemented
* what has NOT been implemented
* current model v1
* current model v2
* current feature store
* current event data
* current evaluation/CTR infrastructure
* current model registry/versioning

## Phase table

Create a table like:

| Phase | File  | Topic           | Status      | Depends On       |
| ----- | ----- | --------------- | ----------- | ---------------- |
| 1     | 01... | ML fundamentals | NOT STARTED | Existing project |
| 2     | 02... | Data/features   | NOT STARTED | Phase 1          |
| 3     | 03... | First ML model  | NOT STARTED | Phase 1–2        |
| ...   | ...   | ...             | ...         | ...              |

Use statuses:

* NOT STARTED
* IN PROGRESS
* COMPLETED
* BLOCKED

Initially everything should be `NOT STARTED`.

## Execution rules

Document that:

1. We work on exactly ONE phase at a time.
2. Within a phase, work on one task at a time.
3. Do not jump ahead.
4. Do not implement future phases prematurely.
5. Before starting a phase, read the previous phase.
6. Before coding, inspect the existing project code relevant to that phase.
7. Do not rewrite working infrastructure unnecessarily.
8. Every phase must contain theory + implementation + experiment + verification.
9. Every completed task must have a verification step.
10. Update the index when a phase is completed.
11. Do not mark a phase complete until its exercises/tests pass.
12. Prefer understanding over abstraction.
13. Start with classical ML before deep learning.
14. Do not introduce LLMs just because this is an AI/ML project.

## Context recovery instructions

Add a section specifically for Cursor:

```text
WHEN STARTING A NEW CONTEXT WINDOW:

1. Read 00_ML_PLAN_INDEX.md.
2. Read ML_CONTEXT.md.
3. Determine the current IN PROGRESS / next NOT STARTED phase.
4. Read that phase file.
5. Read the immediately previous completed phase.
6. Inspect the relevant existing source code.
7. Continue from the first incomplete task.
8. Do not restart completed work.
```

This is extremely important.

---

# ML_CONTEXT.md

Create a compact permanent context file.

This should contain the information Cursor will need repeatedly without rereading the entire project.

Include:

## Existing architecture

```text
Client
  ↓
FastAPI
  ↓
RecommendationService
  ↓
Redis features + PostgreSQL candidates
  ↓
model.predict(features, candidates)
  ↓
ranked recommendations
```

## Model boundary

Clearly state:

```text
RecommendationService = data access/orchestration

Model = mathematical prediction/ranking

Model must NOT:
- access Redis
- access PostgreSQL
- access Kafka
- perform HTTP calls
- know infrastructure details
```

## Current models

Document v1 and v2 exactly as implemented.

## Existing data

Document:

* `user_events`
* `recommendation_items`
* online Redis features
* click/purchase information
* candidate scores
* `last_item_id`

## Existing ML/MLOps infrastructure

Document:

* model registry
* model version
* prediction logs
* CTR
* drift helper
* metrics
* canary
* rollback

## Important project rules

Keep this file concise.

It should be a **stable context file**, not another tutorial.

---

# PHASE FILE REQUIREMENTS

Every phase file must have the following structure:

```markdown
# Phase X — ...

## Objective

## Why This Phase Exists

## Relationship To Existing Recommendation Service

## Prerequisites

## Concepts To Learn

## Tasks

### Task X.1
...

### Task X.2
...

## Practical Exercises

## Implementation Work

## Tests / Verification

## Expected Outcome

## Interview Questions

## Completion Checklist

## What The Next Phase Will Need

## Previous Phase

## Next Phase
```

Each phase must explicitly reference its predecessor and successor.

---

# PHASE CONTENT

## Phase 1 — ML Fundamentals

Teach:

* What is machine learning?
* Model
* Features
* Labels
* Parameters
* Hyperparameters
* Training
* Validation
* Testing
* Inference
* Supervised learning
* Unsupervised learning
* Regression
* Classification
* Ranking
* Overfitting
* Underfitting
* Bias/variance
* Data leakage

Use tiny Python datasets.

Do NOT immediately use the recommendation-service data.

Goal:

I should understand what a trained model actually is before implementing one.

---

# Phase 2 — Data and Feature Engineering

Connect directly to our recommendation data.

Teach:

* raw events
* interaction data
* labels
* positive/negative examples
* feature engineering
* categorical features
* numerical features
* missing values
* normalization
* timestamps
* temporal features
* train/test splitting
* leakage

Use our existing concepts:

```text
click_count
purchase_count
last_item_id
item score
user_id
item_id
event_type
timestamp
```

Important:

Teach why a recommendation model cannot simply train on the same information it would not know at prediction time.

Introduce **point-in-time correctness** conceptually, but do not go deeply into feature-store architecture yet.

---

# Phase 3 — First Classical ML Model

Build the first genuine ML model.

Prefer:

1. Logistic Regression first
2. Decision Tree second
3. Random Forest later

Start with Logistic Regression.

Teach the mathematical intuition.

For example:

```text
features
    ↓
weighted combination
    ↓
sigmoid
    ↓
probability
```

Explain:

* weights
* bias/intercept
* sigmoid
* probability
* loss
* training
* gradient descent conceptually

Do not hide everything behind `.fit()`.

We can use scikit-learn, but first explain what it is doing conceptually.

Then train a model predicting whether a user will click an item.

---

# Phase 4 — Recommendation System Fundamentals

Teach:

* popularity recommendation
* content-based recommendation
* collaborative filtering
* user-item matrix
* implicit feedback
* explicit feedback
* similarity
* nearest neighbors
* matrix factorization
* embeddings
* hybrid recommendation

Relate every concept back to the existing service.

Explicitly compare:

```text
Current v1
Current v2
Classical ML ranking
Collaborative filtering
Hybrid model
```

Explain what is appropriate for our project at each stage.

---

# Phase 5 — Ranking and Evaluation

This is extremely important.

Teach:

Classification metrics:

* accuracy
* precision
* recall
* F1
* ROC-AUC
* log loss

Recommendation metrics:

* Precision@K
* Recall@K
* Hit Rate@K
* MAP@K
* NDCG@K

Explain why recommendation systems care about the order of results.

Build our own small ranking evaluator.

Then compare:

```text
Popularity baseline
Rule-based v2
ML model
```

---

# Phase 6 — Training/Serving Pipeline

Teach:

```text
Training data
    ↓
Feature engineering
    ↓
Training
    ↓
Validation
    ↓
Model artifact
    ↓
Model version
    ↓
Inference service
```

Explain offline vs online.

Then integrate the trained model with our existing model interface.

The model should still expose something conceptually similar to:

```python
model.predict(features, candidates)
```

The service remains responsible for I/O.

---

# Phase 7 — Feature Store and Serving

Connect directly to our Redis/PostgreSQL feature architecture.

Teach:

* offline features
* online features
* feature freshness
* feature versioning
* training-serving skew
* point-in-time correctness
* feature pipelines

Explain how:

```text
PostgreSQL user_events
        ↓
feature computation
        ↓
Redis online features
        ↓
model inference
```

relates to:

```text
historical events
        ↓
training dataset
        ↓
trained model
```

---

# Phase 8 — Model Experimentation

Compare:

```text
v1 popularity
v2 heuristic
ML v3
```

Create experiments around:

* feature changes
* algorithms
* hyperparameters
* training datasets

Record:

* CTR
* Precision@K
* Recall@K
* NDCG@K
* latency
* failure rate

Teach offline evaluation vs online evaluation.

---

# Phase 9 — Model Versioning and Deployment

Connect ML model versions to the existing deployment architecture.

Teach:

* model artifacts
* model versioning
* model registry
* champion/challenger
* shadow testing
* canary
* A/B testing
* rollback

Clearly distinguish:

```text
SERVICE_VERSION
MODEL_VERSION
```

Explain how model v3 could be deployed without rebuilding the entire ML pipeline unnecessarily.

---

# Phase 10 — ML Monitoring and Drift

Connect to the monitoring already implemented.

Teach:

* feature drift
* data drift
* prediction drift
* concept drift
* model degradation
* delayed labels
* feedback loops
* training-serving skew

Relate these to our existing:

* prediction logs
* CTR
* Prometheus metrics
* drift helper

Do not put expensive drift computation inside the synchronous recommendation request.

Preserve the existing design where drift analysis is offline.

---

# Phase 11 — Progressive Model Improvement

Only after the previous phases work.

Experiment progressively with:

1. Logistic Regression
2. Decision Tree
3. Random Forest
4. Gradient Boosting
5. Better feature engineering
6. More ranking-oriented approaches

For every model:

```text
Train
↓
Evaluate
↓
Compare
↓
Understand
↓
Save
↓
Integrate
↓
Monitor
```

Do not introduce complexity without measuring whether it improves the model.

---

# Phase 12 — Advanced Recommendation Systems

Only after the previous phases.

Introduce conceptually first:

* matrix factorization
* embeddings
* ANN
* two-stage recommendation
* candidate generation
* learning-to-rank
* XGBoost/LightGBM ranking
* neural collaborative filtering
* deep recommendation models

Clearly label:

BEGINNER
INTERMEDIATE
ADVANCED

Do not require implementation of everything.

---

# RESEARCH REQUIREMENT

The plan itself should be grounded in current authoritative resources.

Research the current recommended learning/documentation resources for:

* scikit-learn
* recommendation systems
* ranking metrics
* feature engineering
* model evaluation
* ML model deployment
* model monitoring
* recommender systems

Prefer official documentation and high-quality educational sources.

Do not add a huge bibliography.

Each phase should have a small:

```markdown
## Recommended References
```

section containing only resources relevant to that phase.

Do not let research turn the plan into a theoretical academic course.

This is a practical engineering learning project.

---

# IMPORTANT: DO NOT IMPLEMENT THE ML YET

At this stage your job is ONLY to:

1. Analyze `ML_Implementation_Plan.md`.
2. Analyze the existing recommendation-service structure.
3. Identify the ML gaps.
4. Create the multi-file plan.
5. Create `00_ML_PLAN_INDEX.md`.
6. Create `ML_CONTEXT.md`.
7. Create all numbered phase files.
8. Make the phases logically dependent.
9. Make the plan suitable for multiple Cursor context windows.

Do NOT:

* modify the existing application code
* install ML libraries
* train models
* create datasets
* create Docker services
* change Redis/Postgres/Kafka
* rewrite model.py
* implement Phase 1
* skip ahead

This task is documentation/planning only.

---

# QUALITY CHECK BEFORE FINISHING

After creating the files, review them as if another developer opened a completely new Cursor context window.

Ask:

> If Cursor only reads `00_ML_PLAN_INDEX.md` and `ML_CONTEXT.md`, can it determine exactly where we are and what it should read next?

Then verify:

* no phase depends on an undefined previous concept
* no major ML concept is duplicated unnecessarily
* fundamentals come before implementation
* classical ML comes before deep learning
* recommendation concepts connect to our actual project
* evaluation comes before claiming a model is better
* training/serving separation is clear
* model and infrastructure boundaries remain clear
* every phase has completion criteria
* every phase references previous/next phase
* future context recovery is explicitly documented

At the end, provide a short summary of the files created and identify:

**NEXT ACTION: Start Phase 1, Task 1.1**

Do not start Task 1.1 yet.
