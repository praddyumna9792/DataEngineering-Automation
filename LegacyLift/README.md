# LegacyLift — Automated Historical Data Migration Platform

> **Tagline:** Move Historical Data. Automate the Complexity.

**LegacyLift** is an enterprise-grade automated historical data migration platform designed to transfer large analytical datasets from **Google BigQuery** to **Snowflake** by leveraging **Apache Iceberg**, **Google Cloud Storage**, **Snowflake External Volumes**, and **Native Table Materialization**.

---

## 🌟 Key Features

1. **Minimal User Input**: Standard migrations require only **two mandatory inputs** on the primary screen:
   - BigQuery source table name (e.g. `customer_history`)
   - Snowflake target table name (e.g. `CUSTOMER_HISTORY`)
   *(All project IDs, datasets, databases, schemas, buckets, external volumes, and batch boundaries are automatically discovered or derived).*
2. **Table-Name Resolution & Ambiguity Protection**: Discovers authorized datasets and schemas; prompts the user with candidates if a table name is ambiguous.
3. **Mandatory Existing-Target Detection**:
   - **Case A (Target does not exist)**: Automatically generates `CREATE TABLE` statements.
   - **Case B (Target already exists)**: **Suppresses redundant CREATE TABLE DDL**, compares schema compatibility, and selects deduplicating `MERGE INTO` or safe `APPEND`.
4. **Four-Stage SQL Pipeline Engine**:
   - **Stage 1**: BigQuery export to Apache Iceberg / Parquet format in GCS.
   - **Stage 2**: Target Schema Blueprint contract DDL.
   - **Stage 3**: Snowflake External Volume and GCS Stage registration.
   - **Stage 4**: Snowflake native table materialization with batch-aware loading.
5. **Interactive SQL Review & Governance**: Tabbed SQL editors, syntax validation, safety checks, and strict approval invalidation upon code modification.
6. **Stateful Batch Processing & Durable Checkpoints**:
   - Partitions historical datasets by date/timestamp or PK ranges.
   - Persists batch checkpoints to local SQLite database (`legacylift.db`).
   - Supports safe **resume after failure**, skipping completed batches without duplicate data ingestion.
7. **End-to-End Data Parity Reconciliation**: Verifies row counts, discrepancies, and checksums between source and target.
8. **Automated Pipeline Artifact Generation**:
   - 🌬️ **Apache Airflow DAG** (`.py`)
   - ⚡ **Dataproc PySpark Iceberg Job** (`.py`)
   - 🧱 **Snowflake dbt Project** (`dbt_project.yml`, models, sources, and schema tests)
9. **Simulation Mode & Zero-Cloud Testing**: Fully functional out of the box with deterministic sample catalogs and simulated batch recovery workflows.

---

## 🏗️ Project Architecture

```text
LegacyLift/
├── app.py                      # Streamlit application entrypoint
├── config/                     # Configuration and environment profiles
│   ├── settings.py
│   └── __init__.py
├── core/                       # Core domain engines and algorithms
│   ├── models.py               # Domain dataclasses and schemas
│   ├── metadata_discovery.py   # BQ and Snowflake discovery service
│   ├── schema_manager.py       # Type mapping and schema comparison
│   ├── mapping_manager.py      # CSV/XLSX dynamic mapping parsing
│   ├── target_table_manager.py # Mandatory Case A/B Snowflake target logic
│   ├── batch_manager.py        # Date/PK range batch partitioning
│   ├── sql_generator.py        # Four-stage SQL generation engine
│   ├── sql_validator.py        # Syntax safety and destructive statement detector
│   ├── execution_engine.py     # Stateful batch executor with checkpoints
│   ├── reconciliation.py       # Row count parity and checksum validator
│   ├── migration_planner.py    # Unifies discovery, planning, and approvals
│   └── __init__.py
├── connectors/                 # Cloud service adapters (Simulation & Live)
│   ├── base.py                 # Abstract connector interfaces
│   ├── bigquery_connector.py
│   ├── snowflake_connector.py
│   ├── gcs_connector.py
│   ├── airflow_connector.py
│   └── dataproc_connector.py
├── generators/                 # Pipeline artifact generators
│   ├── airflow_generator.py
│   ├── dataproc_generator.py
│   └── dbt_generator.py
├── persistence/                # Durable SQLite storage
│   ├── db.py                   # Schema initialization
│   └── repositories.py         # Plans, runs, checkpoints, and settings
├── simulation/                 # Offline mock catalog
│   └── mock_catalog.py
├── ui/                         # Streamlit UI views and custom styles
│   ├── styles.py
│   ├── view_overview.py
│   ├── view_new_migration.py
│   ├── view_review.py
│   ├── view_execution.py
│   ├── view_artifacts.py
│   ├── view_history.py
│   └── view_settings.py
├── sample_data/                # Sample mappings and schemas
├── tests/                      # Automated pytest suite (32 tests)
├── docs/                       # Technical architecture and setup guides
│   ├── ARCHITECTURE.md
│   ├── CLOUD_SETUP.md
│   └── USER_GUIDE.md
├── .env.example
├── .gitignore
├── requirements.txt
├── run_app.bat                 # Windows launcher
└── run_app.sh                  # Linux/macOS launcher
```

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.10+
- Dependencies: `streamlit`, `pandas`, `openpyxl`, `sqlparse`, `pydantic`, `pytest`

### 2. Install Dependencies
```bash
cd LegacyLift
pip install -r requirements.txt
```

### 3. Run Application
```bash
# Windows
run_app.bat

# Linux / macOS
chmod +x run_app.sh
./run_app.sh
```
Or directly:
```bash
python -m streamlit run app.py
```
Open **`http://localhost:8501`** in your browser.

---

## 🧪 Automated Testing

LegacyLift comes with a comprehensive test suite covering unit tests, integration tests, and end-to-end simulation workflows without requiring cloud credentials:

```bash
python -m pytest LegacyLift/tests -v
```

### Test Coverage Highlights (32 Tests Passing):
- `test_metadata_discovery.py`: Exact resolution, ambiguous table detection, non-existent table errors.
- `test_schema_mapping.py`: BQ to Snowflake type conversions, JSON schema parsing, CSV mapping inspection, compatibility matrices.
- `test_target_table_manager.py`: Case A (new target DDL), Case B (existing target DDL suppression), incompatible schema alerts.
- `test_sql_generator.py`: Four SQL stages, quoting, expressions (`UPPER`, `TRIM`, `COALESCE`), conditional DDL suppression.
- `test_batch_manager.py`: Partition boundaries, row estimation, primary key chunking.
- `test_execution_engine.py`: Approval enforcement, stateful checkpointing, simulated batch failure and resume.
- `test_generators.py`: Valid Airflow DAG generation, Dataproc PySpark script, Snowflake dbt project and schema tests.
- `test_reconciliation.py`: Parity score calculations, delta identification.
- `test_e2e_simulation.py`: Complete user journeys from 2-input entry to execution and approval invalidation upon SQL editing.

---

## ☁️ Transition to Live Cloud Execution

1. Copy `.env.example` to `.env` and fill in your GCP project and Snowflake credentials.
2. In the UI, navigate to **Settings** and toggle mode to **LIVE**.
3. Click the test buttons to verify your BigQuery, Snowflake, and GCS permissions.
4. Detailed cloud setup instructions are available in [docs/CLOUD_SETUP.md](docs/CLOUD_SETUP.md).

---

## 📄 License
Commercial Data Engineering Platform — LegacyLift. All rights reserved.
