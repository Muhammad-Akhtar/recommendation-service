"""Task 3.6 — Decision tree as a second classical model.

A tree splits on feature thresholds (max_depth=3). Different inductive bias
from logistic regression: piecewise-constant regions instead of a linear
log-odds surface. Still classical ML — not a neural net. Train accuracy
alone is not enough; we also score the temporal test split.
"""

from __future__ import annotations

from sklearn.tree import DecisionTreeClassifier, export_text

from ml.phase02_features.encode import NUMERIC_FEATURE_NAMES
from ml.phase02_features.splits import temporal_split
from ml.phase03_classical_ml.train_logreg import labeled_matrix, prepared_rows


def fit_tree(
    *,
    max_depth: int = 3,
) -> tuple[DecisionTreeClassifier, float, float, str]:
    train, test = temporal_split(prepared_rows())
    X_train, y_train = labeled_matrix(train)
    X_test, y_test = labeled_matrix(test)
    tree = DecisionTreeClassifier(max_depth=max_depth, random_state=0)
    tree.fit(X_train, y_train)
    train_acc = float(tree.score(X_train, y_train))
    test_acc = float(tree.score(X_test, y_test))
    text = export_text(tree, feature_names=list(NUMERIC_FEATURE_NAMES))
    return tree, train_acc, test_acc, text


def main() -> None:
    tree, train_acc, test_acc, text = fit_tree()
    print("feature_importances:")
    for name, imp in zip(NUMERIC_FEATURE_NAMES, tree.feature_importances_, strict=True):
        print(f"  {name:24s} {float(imp):.3f}")
    print(f"train_acc={train_acc:.3f} temporal_test_acc={test_acc:.3f}")
    print(text)


if __name__ == "__main__":
    main()
