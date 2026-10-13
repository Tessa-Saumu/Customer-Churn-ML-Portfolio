# Customer churn: model integration and evaluation

I worked on a mentored team capstone that turned a telecom customer snapshot into a local data pipeline, churn prediction service and Power BI report. My work focused on connecting the trained model to the application, adding automated tests, reviewing changes and checking the components together.

The dataset contains 7,043 customer records. This is a sample analytics project; I did not measure a reduction in churn or deploy a service for customers. The [dataset provenance](docs/data_provenance.md) records its identity and unresolved redistribution permission.

## What I contributed

I connected the application programming interface (API) to the trained model, reconciled its request fields with the training schema, and added configurable artifact paths. Integration testing exposed an outcome-derived `churn_score` input; it was removed from training. I also wrote tests for data preparation, API behavior and prediction, contributed SQL-view checks, and coordinated technical review and final integration.

The data preparation, initial training, API scaffold and Power BI report had other team owners. Mentor Adeyeri Michael contributed scaffolding and customer pagination. [CONTRIBUTORS.md](CONTRIBUTORS.md) records those boundaries. This personal portfolio copy also contains subsequent repairs to evaluation, reproducibility and packaging.

## How it works

```mermaid
flowchart LR
    CSV[Customer CSV] --> ETL[Clean and load]
    ETL --> DB[SQLite database]
    DB --> Views[SQL views and customer KPIs]
    DB --> Train[Training-only model comparison]
    Train --> Pair[Selected model and its evaluation report]
    Views --> API[FastAPI service]
    Pair --> API
    Views -.-> BI[Power BI report]
```

The extract, transform and load (ETL) scripts clean the comma-separated values (CSV) file and load SQLite. Structured Query Language (SQL) views summarize churn by contract and tenure. The FastAPI service returns paginated customers, whole-dataset key performance indicators (KPIs), predictions and model metrics. The Power BI file uses imported data; I have not verified its refresh path in this run.

## Evaluation and current result

I reserve 20% of the rows for the final test and use the other 80% to compare models. The split keeps similar proportions of churned and retained customers in both parts—called a stratified split—and uses a fixed random seed of 42 so the same rows can be selected again. Five-fold cross-validation divides the training data into five parts: each candidate learns from four parts and is checked on the fifth, rotating through all five. Data preparation is fitted only on the learning part. A classifier that always predicts the majority class provides the baseline. After selecting the winner by its risk-ranking score, I refit it on the training portion and evaluate it on the untouched 1,409-row final test. I did not tune the models or the prediction threshold.

The current recorded run used **Python 3.11.12 on Windows** and selected Logistic Regression:

| Holdout measure | Logistic Regression | Majority-class baseline |
|---|---:|---:|
| Accuracy: share classified correctly | 0.8020 | 0.7346 |
| Precision: share of predicted churners who churned | 0.6480 | 0.0000 |
| Recall: share of actual churners identified | 0.5561 | 0.0000 |
| ROC AUC: area under the receiver operating characteristic curve | 0.8494 | 0.5000 |

The confusion matrix is `[[922, 113], [166, 208]]`: the model correctly identified 208 churners and missed 166. Its ranking performance beats the baseline, but that does not establish reliable retention decisions.

[evaluation/model_comparison.md](evaluation/model_comparison.md) is the current result source. [The run record](docs/current_run.md) explains the environment and checks. Older Linux results and the earlier selected-on-test comparison are explicitly historical under `evaluation/reproduction/` and `evaluation/legacy/`; they are not current competing results. Native numerical libraries can produce different fits across systems, so I do not claim identical numbers on every machine.

Training now saves the selected model with its holdout metrics and the exact report checksum. `/model-metrics` checks that the report belongs to the loaded prediction model. It rejects a restored or edited report from another run. Tests and experiments that redirect their report also redirect their model, so they cannot silently replace the serving model.

## Run locally

Supported runtime: **Python 3.11**; the current recorded run uses the patch version in `.python-version`. Install the pinned requirements in an isolated environment. From PowerShell 7 on Windows:

```powershell
git clone https://github.com/Tessa-Saumu/Customer-Churn-ML-Portfolio.git
cd Customer-Churn-ML-Portfolio
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set API_KEY=local-dev-key
.venv/Scripts/python.exe database/init_db.py
.venv/Scripts/python.exe etl/load_to_db.py
.venv/Scripts/python.exe database/init_views.py
.venv/Scripts/python.exe training/evaluate_models.py
.venv/Scripts/python.exe scripts/generate_model_comparison_csv.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

After the server is ready, open a second terminal at the repo root:

```powershell
$env:API_KEY='local-dev-key'
./scripts/verify_endpoints.ps1
```

The same Python pipeline commands work on Linux using the environment's Python executable. The Bash acceptance script also needs `curl` and `jq`: `API_KEY=local-dev-key ./scripts/verify_endpoints.sh`. Restart the API after training so predictions and metrics both use the newly saved run. The database and model are generated locally and are not committed.

## Demo and limits

![Churn Drivers page from the team Power BI report](dashboard/screenshots/churn_drivers.jpg)

The pictured dataset totals were checked against the SQL views in the historical release verification. Its `Avg Churn Score` card is an outcome-derived source field, not an input to the trained model. The [Power BI file](dashboard/churn_dashboard.pbix) and other captures remain historical; the Model Predictions page does not represent the current evaluation. [API examples](docs/api_examples.md) show the current local contract.

This is a local project. There is no hosted deployment, production usage or measured business impact. GitHub Actions remains blocked at the account level; I do not claim a green CI (continuous integration) run. Docker and the optional Streamlit client remain unverified.

The static snapshot has no time index, so this evaluation says nothing about future periods or other carriers. Logistic Regression reaches its 1,000-iteration limit without converging. Recall remains limited, and no calibration or threshold study was performed. Inputs above 72 months still have an open tenure-bucket edge. The API uses a shared key and loads its model at startup; it is not a production security design.
