# syntax=docker/dockerfile:1

# ============================================================
# Stage 1 — Build database and train the ML model
# ============================================================
# Base image aligned 2026-10-05 with the one supported runtime (.python-version,
# docs/reproduction_record.md): Python 3.11. This file claimed Python 3.12 before
# that, but 3.12 had never been run and could not be tested here. NOTE: no Docker
# build was executed in this environment (no daemon) -- the container path stays
# documented-not-verified either way.
FROM python:3.11-slim AS trainer

WORKDIR /app

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Python dependencies
# ------------------------------------------------------------
# requirements.txt constrains itself with -c requirements.lock.txt, so both files
# must be in the build context for the pinned install to resolve.
COPY requirements.txt requirements.lock.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# Application source
# ------------------------------------------------------------
COPY app/ ./app/
COPY database/ ./database/
COPY etl/ ./etl/
COPY training/ ./training/
COPY evaluation/ ./evaluation/
COPY sql/ ./sql/
COPY utils/ ./utils/
COPY scripts/ ./scripts/
COPY predict.py .

# ------------------------------------------------------------
# Raw dataset
# ------------------------------------------------------------
COPY data/raw/ ./data/raw/

# ------------------------------------------------------------
# Create generated-artifact directories
# ------------------------------------------------------------
RUN mkdir -p database models evaluation

# ------------------------------------------------------------
# Build database
# ------------------------------------------------------------
RUN python database/init_db.py

RUN python etl/load_to_db.py

RUN python database/init_views.py

# ------------------------------------------------------------
# Train models
# ------------------------------------------------------------
RUN python training/evaluate_models.py

# ------------------------------------------------------------
# Verify trained model exists
# ------------------------------------------------------------
RUN test -f models/best_model.pkl \
    || (echo "ERROR: models/best_model.pkl was not created" && exit 1)

# ------------------------------------------------------------
# Verify evaluation report exists
# ------------------------------------------------------------
RUN test -f evaluation/model_comparison.md \
    || (echo "ERROR: evaluation/model_comparison.md was not created" && exit 1)


# ============================================================
# Stage 2 — Runtime API
# ============================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# ------------------------------------------------------------
# Runtime environment
# ------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=models/best_model.pkl \
    MODEL_METRICS_PATH=evaluation/model_comparison.md

# ------------------------------------------------------------
# Python dependencies
# ------------------------------------------------------------
# requirements.txt constrains itself with -c requirements.lock.txt, so both files
# must be in the build context for the pinned install to resolve.
COPY requirements.txt requirements.lock.txt ./

RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# ------------------------------------------------------------
# FastAPI application
# ------------------------------------------------------------
COPY --from=trainer /app/app/ ./app/

# ------------------------------------------------------------
# Prediction entry point
# ------------------------------------------------------------
COPY --from=trainer /app/predict.py ./predict.py

# ------------------------------------------------------------
# Training package
#
# predict.py imports:
#
#     from training.preprocessing import prepare_features
#
# Therefore training/ must exist in the runtime image.
# ------------------------------------------------------------
COPY --from=trainer /app/training/ ./training/

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
COPY --from=trainer /app/utils/ ./utils/

# ------------------------------------------------------------
# Database generated during build
# ------------------------------------------------------------
COPY --from=trainer /app/database/ ./database/

# ------------------------------------------------------------
# Trained model generated during build
# ------------------------------------------------------------
COPY --from=trainer /app/models/best_model.pkl ./models/best_model.pkl

# ------------------------------------------------------------
# Evaluation report
# ------------------------------------------------------------
COPY --from=trainer /app/evaluation/model_comparison.md ./evaluation/model_comparison.md

# ------------------------------------------------------------
# API port
# ------------------------------------------------------------
EXPOSE 8000

# ------------------------------------------------------------
# Start FastAPI
# ------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]