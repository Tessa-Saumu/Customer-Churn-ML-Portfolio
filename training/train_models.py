import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from training.preprocessing import build_preprocessor
from training.train_test_split import RANDOM_STATE, split_training_data

# Set up logging
logger = logging.getLogger(__name__)

# Name of the naive reference model. It is *not* a candidate: it is reported
# alongside the five real models so the comparison has a floor, and it is never
# eligible for selection (see training/evaluate_models.py).
BASELINE_MODEL_NAME = "DummyClassifier (baseline)"


def build_candidate_models() -> dict[str, ClassifierMixin]:
    """
    The five candidate models compared by the evaluation protocol.

    ADDED 2026-10-06 (Phase 3 / FGA-05): the same five definitions previously
    lived inline in `train_models()`. They are extracted here so that the
    cross-validated selection loop and the final refit provably use one
    definition of each model, rather than two copies that could drift.

    No model definition, hyperparameter or seed changed in this extraction:
    `LogisticRegression(max_iter=1000)`, Decision Tree, Random Forest, XGBoost
    (`eval_metric="logloss"`) and LightGBM, all with `random_state=42` and no
    tuning (no hyperparameter search is in scope).
    """
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=1000, random_state=RANDOM_STATE
        ),
        "Decision Tree": DecisionTreeClassifier(random_state=RANDOM_STATE),
        "Random Forest": RandomForestClassifier(random_state=RANDOM_STATE),
        "XGBoost": XGBClassifier(eval_metric="logloss", random_state=RANDOM_STATE),
        "LightGBM": LGBMClassifier(random_state=RANDOM_STATE),
    }


def build_baseline_model() -> ClassifierMixin:
    """
    The naive reference model: a `DummyClassifier` that predicts the training
    class prior. It exists to answer "what does the selected model have to beat
    for this problem?", not to compete for selection.

    `strategy="prior"` is deliberate: it is the majority/prior baseline the
    audit asks for (FGA-05), and because it ignores the features it bounds ROC
    AUC at 0.5 by construction.
    """
    return DummyClassifier(strategy="prior", random_state=RANDOM_STATE)


def build_pipeline(model: ClassifierMixin, X: pd.DataFrame) -> Pipeline:
    """
    Wrap `model` in a fresh, *unfitted* preprocessor built for `X`.

    A new preprocessor per fit is what keeps preprocessing inside whatever data
    it is fitted on: in the cross-validation loop that is the fold's training
    rows only, so no category or distribution information from validation or
    holdout rows can reach the transformer. `Pipeline.fit` then fits both steps
    on exactly the rows it is given.
    """
    return Pipeline(
        steps=[("preprocessor", build_preprocessor(X)), ("classifier", model)]
    )


# Train a single model with the given name, model instance, preprocessor, and training data.
def train_single_model(
    model_name: str,
    model,
    preprocessor,
    X_train,
    y_train,
) -> Pipeline:
    # Log the start of model training
    logger.info("Training %s model...", model_name)

    # Create a pipeline that includes the preprocessor and the model
    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("classifier", model)])

    # Fit the pipeline to the training data
    pipeline.fit(X_train, y_train)

    # Log the completion of model training
    logger.info("%s model training complete.", model_name)
    return pipeline


# Training multiple models and return a dictionary of trained models.
def train_models() -> tuple[dict[str, Pipeline], pd.DataFrame, pd.Series]: 
    """Fit every candidate on the outer training portion (no evaluation here).

    Kept as the "train all five candidates" helper it always was, now using
    `build_candidate_models()` so its definitions cannot drift from the ones the
    evaluation protocol selects between. The Phase 3 protocol itself does not
    call this function: it fits candidates inside training-side folds and refits
    only the frozen winner (training/evaluate_models.py::evaluate_all_models).
    """
    
    # Split the training data into train and test sets
    logger.info("Splitting training data...")
    X_train, X_test, y_train, y_test, preprocessor = split_training_data()

    # Define a dictionary of models to be trained
    models = build_candidate_models()

    # Train each model and store the trained models in a dictionary
    trained_models = {}
    for model_name, model in models.items():
        trained_model = train_single_model(
            model_name,
            model,
            preprocessor,
            X_train,
            y_train,
        )
        trained_models[model_name] = trained_model

        logger.info( "%s added to trained models.", model_name)
    return trained_models, X_test, y_test

# If the script is run directly, set up logging and call the train_models function
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    trained_models, X_test, y_test = train_models()
    logger.info("All models trained successfully.")