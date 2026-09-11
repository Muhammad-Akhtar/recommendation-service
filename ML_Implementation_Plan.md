> **Executable multi-file plan:** start at [`docs/ml/00_ML_PLAN_INDEX.md`](docs/ml/00_ML_PLAN_INDEX.md) (then [`docs/ml/ML_CONTEXT.md`](docs/ml/ML_CONTEXT.md)). This file is the original brief; do not re-create the phase docs.

I have already built a production-oriented Python recommendation microservice using FastAPI, Pydantic, PostgreSQL, Redis, Kafka, Avro/Schema Registry, Kubernetes, pytest, Prometheus metrics, OpenTelemetry, structured logging, model versioning, canary deployments, HPA, graceful degradation, retries, circuit breakers, and a DLQ.

I now want to thoroughly learn and practice the **AI/ML/model-related concepts that were not covered deeply enough** in that project.

Use the implementation summary I provide as the source of truth for what is already implemented. Do NOT restart the entire recommendation-service project and do NOT reteach FastAPI, Redis, Kafka, Kubernetes, Docker, CI, or general microservice architecture unless a concept is directly needed for the ML work.

## My current ML implementation

The current recommendation model is intentionally simple:

* Model v1 ranks the top 5 candidates by PostgreSQL popularity score.
* Model v2 calculates:
  `score + click_count × 0.01 + purchase_count × 0.05 + 0.5 if item == last_item_id`
* The model receives `features` and `candidates`.
* The model itself does NOT access Redis, PostgreSQL, or Kafka.
* RecommendationService is responsible for loading features/candidates and passing them to the model.
* The model only performs ranking.
* MODEL_VERSION is separated from SERVICE_VERSION.
* Prediction logs, CTR by model version, and offline drift helpers already exist.
* The architecture deliberately keeps expensive work outside the synchronous recommendation request path.

The relevant architecture is:

GET /recommendations/{user_id}
→ Redis response cache
→ Redis online features + PostgreSQL candidate catalog
→ model.predict(features, candidates)
→ cache result + impression/prediction logging
→ response

The model boundary is:

RecommendationService:
load features
load candidates
model.predict(features, candidates)

Model:
receive features + candidates
calculate scores
rank candidates
return recommendations

## What I want to learn

Create a structured, hands-on ML learning path specifically around this existing implementation.

Start at beginner level where necessary. Assume I understand Python reasonably well but want to properly understand the ML concepts rather than blindly using libraries.

Teach me progressively through theory → small example → implementation → experiment → evaluation → integration.

### Phase 1 — ML fundamentals

Teach and practice:

1. What a machine-learning model actually is
2. Features
3. Labels/targets
4. Training data vs inference data
5. Parameters vs hyperparameters
6. Training, validation, and test datasets
7. Regression vs classification vs ranking
8. Supervised vs unsupervised learning
9. Overfitting and underfitting
10. Bias vs variance
11. Data leakage
12. Feature engineering
13. Normalization/standardization
14. Missing values and categorical data

Use tiny Python datasets and formulas first.

Do not just explain terminology. Make me implement small examples.

### Phase 2 — Replace our rule-based model with real ML

Our current v1/v2 models are rule-based ranking models.

Teach me how we would evolve this into an actual learned recommendation model.

Start with a very small dataset such as:

user_id
item_id
click_count
purchase_count
last_item_id
item_popularity
category
timestamp
clicked

Explain why `clicked` can become a training label.

Build a simple model first, such as:

* Logistic Regression
* Decision Tree
* Random Forest or Gradient Boosting

Explain exactly:

features → model → predicted probability/score → ranking

For example:

P(user will click item | user features, item features)

Then rank candidate items by predicted probability.

### Phase 3 — Recommendation-system fundamentals

Teach the difference between:

1. Popularity-based recommendation
2. Content-based recommendation
3. Collaborative filtering
4. User-item interaction matrices
5. Explicit vs implicit feedback
6. Nearest-neighbor recommendation
7. Matrix factorization
8. Embeddings
9. Hybrid recommendation systems
10. Candidate generation vs ranking

Relate every concept back to my existing architecture.

Explain which approach would realistically fit my current project and which approaches are unnecessarily complex at this stage.

### Phase 4 — Build a small real recommendation model

Create a small local dataset.

Then implement a complete offline pipeline:

raw interaction data
→ cleaning
→ feature engineering
→ train/validation/test split
→ model training
→ prediction
→ ranking
→ evaluation
→ save model artifact

Prefer scikit-learn initially.

Do NOT jump directly to PyTorch, deep learning, transformers, or LLMs.

I want to understand classical ML first.

Use Python files that I can run locally.

Every important section should contain comments explaining what is happening.

### Phase 5 — Model evaluation

Teach and implement:

Classification metrics:

* accuracy
* precision
* recall
* F1
* ROC-AUC
* log loss

Recommendation/ranking metrics:

* Precision@K
* Recall@K
* Hit Rate@K
* MAP@K
* NDCG@K

Explain why normal classification accuracy is often insufficient for recommendation systems.

Create a small example where two recommendation models have similar accuracy but very different ranking quality.

Then compare them using ranking metrics.

### Phase 6 — Train/serve separation

Explain the difference between:

offline training
vs
online inference.

Design:

training pipeline
→ model artifact
→ model registry/version
→ recommendation service
→ model.predict()

Show how this fits into my existing `model.py` / `model_registry.py` structure.

The trained model should not directly access:

Redis
PostgreSQL
Kafka

The service should load data and pass the model the required features.

### Phase 7 — Feature engineering and feature store

Relate this directly to my existing Redis/PostgreSQL feature-store implementation.

Teach:

* offline features
* online features
* feature freshness
* point-in-time correctness
* training-serving skew
* feature pipelines
* feature versioning

Use my existing examples:

click_count
purchase_count
last_item_id

Show how those features could be calculated from `user_events`.

Explain why calculating features differently during training and serving can produce bad models.

### Phase 8 — Model experimentation

Teach how to compare:

baseline popularity model
vs
rule-based v2
vs
ML model

Create an experiment table containing:

model_version
served
clicked
CTR
Precision@K
Recall@K
NDCG@K
latency

Explain offline evaluation vs online evaluation.

Then explain why offline metrics alone cannot prove that a model is better in production.

### Phase 9 — Model versioning and deployment

Connect this to the existing v1/v2 Kubernetes deployment.

Teach:

* model artifact versioning
* model schema/version compatibility
* model registry concepts
* shadow deployment
* canary deployment
* A/B testing
* rollback
* champion/challenger models

Explain the difference between:

SERVICE_VERSION
MODEL_VERSION

Then show how:

model v1
model v2
model v3

could be deployed safely without changing the entire application.

### Phase 10 — Monitoring ML models

I already implemented prediction logs, CTR, Prometheus metrics, and offline drift helpers.

Now teach the ML concepts behind them:

1. Data drift
2. Concept drift
3. Prediction drift
4. Feature drift
5. Model performance degradation
6. Feedback loops
7. Training-serving skew
8. Monitoring delayed labels
9. Model quality monitoring

Explain exactly what should be monitored in a recommendation system.

Use practical examples rather than abstract definitions.

### Phase 11 — Improve the model progressively

After the first simple ML model works, progressively experiment with:

1. Logistic Regression
2. Decision Tree
3. Random Forest
4. Gradient Boosting
5. Better feature engineering
6. Ranking-oriented approaches

At each step:

* train it
* evaluate it
* compare it against the baseline
* understand why it improved or worsened
* save the model
* integrate it through the existing model interface

Do not introduce a more complicated algorithm just because it is popular.

### Phase 12 — Advanced concepts only after fundamentals

Only after the classical ML recommendation pipeline is understood, introduce:

* matrix factorization
* embeddings
* approximate nearest neighbor search
* two-stage recommendation systems
* learning-to-rank
* XGBoost/LightGBM ranking
* neural collaborative filtering
* deep recommendation models

Clearly label these as beginner/intermediate/advanced.

Do not make me implement all of them immediately.

## Important teaching rules

1. This is a learning project, not just a code-generation task.
2. Do not skip fundamentals.
3. Do not give me huge amounts of code at once.
4. Proceed step-by-step.
5. Give me one task at a time.
6. After each task, wait for me to say it is completed before moving on.
7. Explain formulas in plain English.
8. Use tiny datasets before real datasets.
9. Prefer scikit-learn before PyTorch.
10. Explain WHY before introducing a library.
11. Make me inspect data and model outputs.
12. Include deliberate experiments where I change values and observe the effect.
13. Include common mistakes and failure cases.
14. Include pytest tests where they make sense.
15. Keep the existing recommendation-service architecture intact unless we intentionally decide to modify it.
16. Do not pretend that our existing popularity/rule-based model is an ML model just because the code is called `model.py`.
17. Clearly distinguish:

    * heuristic/rule-based recommendation
    * classical machine learning
    * deep learning
    * generative AI
18. Do not introduce LLMs unless they are actually relevant to recommendation modeling.
19. Keep everything local and reproducible.
20. Avoid unnecessarily large datasets or models.

## Research requirements

Before teaching the roadmap, research the current recommended practices for beginner-to-intermediate recommendation-system ML using authoritative sources.

Prioritize:

* scikit-learn official documentation
* Microsoft Recommenders documentation
* Google recommendation-system / ML documentation
* TensorFlow Recommenders documentation when relevant
* XGBoost documentation when relevant
* academic papers only when they materially help explain a concept

Do not blindly follow tutorials. Compare approaches and explain which concepts are relevant to my architecture.

Clearly separate:

A. Concepts already implemented in my project
B. Concepts partially implemented
C. Concepts not yet implemented
D. Concepts worth learning next
E. Advanced concepts that can be postponed

## Final objective

By the end, I should be able to explain and implement the complete ML lifecycle:

data
→ feature engineering
→ training
→ validation
→ evaluation
→ model artifact
→ model version
→ deployment
→ online inference
→ recommendation ranking
→ feedback
→ monitoring
→ retraining

And I should be able to explain how that lifecycle connects to the recommendation microservice I already built.

Start by giving me:

1. A gap analysis of the ML concepts in my existing implementation.
2. The recommended learning roadmap.
3. The exact first task.
4. The files I should create.
5. The commands to run.
6. A small exercise I must complete myself.

Do not start with advanced ML. Start with the first missing fundamental and build from there.
