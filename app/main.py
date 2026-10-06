"""
Issue #10 -- FastAPI Scaffold -- app/main.py

CHANGED (2026-10-05, Phase 2 / FGA-03+FGA-10 config cleanup): `load_dotenv()`
now runs BEFORE the router import. Importing `app.api.routes` transitively
imports `app.services.metrics_service` (which resolves MODEL_METRICS_PATH at
module level) and `predict` (which resolves MODEL_PATH and joblib-loads the
model at module level). With the router imported first, a `.env`-supplied
MODEL_METRICS_PATH was silently ignored — only a real exported environment
variable (e.g. the Dockerfile's ENV) took effect, while `.env.example` and the
README documented it as a supported setting. Ordering is guarded by
tests/test_reproducibility.py.
"""

import logging

from dotenv import load_dotenv

# Must stay above the router import -- see the module docstring. The two imports
# below are therefore deliberately NOT at the top of the file (E402); the ordering
# is enforced by tests/test_reproducibility.py rather than by import position.
load_dotenv()

from fastapi import FastAPI

from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Customer Churn Prediction & BI Platform API")
app.include_router(router)
