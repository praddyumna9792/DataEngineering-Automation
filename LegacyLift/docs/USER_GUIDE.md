# LegacyLift User Guide

Welcome to **LegacyLift — Automated Historical Data Migration Platform**. This guide explains how to use the platform to migrate historical data from BigQuery to Snowflake.

---

## 1. Quick Start Walkthrough

### Step 1: Start the Application
Run the launcher script:
```bash
# On Windows
run_app.bat

# On Linux or macOS
./run_app.sh
```
Open your browser at `http://localhost:8501`.

---

### Step 2: The Two Mandatory Inputs
Navigate to the **New Migration** tab.

Enter only two details:
1. **BigQuery Source Table Name**: `customer_history`
2. **Snowflake Target Table Name**: `CUSTOMER_HISTORY`

*(Optional)*:
- If you have a custom transformation mapping sheet, upload your CSV/XLSX file.
- If you have an existing schema contract, upload your JSON or CSV file.
- Or simply click one of the **Quick Test Presets** to test different scenarios instantly!

Click **🚀 Discover Metadata & Plan Migration**.

---

### Step 3: Migration Review & Existing-Table Handling
LegacyLift inspects both cloud environments:
- **Case A (New Target)**: If the Snowflake table does not exist, LegacyLift generates the required `CREATE TABLE` DDL.
- **Case B (Existing Target)**: If the Snowflake table already exists (such as `CUSTOMER_HISTORY`), LegacyLift **suppresses redundant CREATE TABLE statements**, compares the schemas, and selects an idempotent `MERGE INTO` or `APPEND` strategy.

Review the four generated SQL stages in the tabbed editor:
- **Stage 1**: BigQuery to Iceberg Export (GCS)
- **Stage 2**: Target Schema Blueprint
- **Stage 3**: Snowflake External Volume & Staging
- **Stage 4**: Snowflake Native Materialization & Ingestion

> **Note on Governance**: You can edit any SQL query directly. If you modify any SQL stage after approving, the approval is immediately invalidated and you must re-validate before execution!

Click **🛡️ Approve Migration Plan**.

---

### Step 4: Execution Center & Recovery
Click **⚡ Proceed to Execution Center**.

Click **🚀 Start Approved Migration**.
- Watch real-time batch checkpoints.
- Review duration, rows migrated, and active logs.

**Testing Interruption & Resume**:
- Check the box `Simulate transient error on Batch 2`.
- Run the migration: Batch 1 completes, Batch 2 fails with a simulated network timeout.
- Click **🔄 Resume Interrupted Migration**: Notice that **Batch 1 is skipped because it is already checkpointed**, and execution safely resumes from Batch 2!

---

### Step 5: Export Generated Pipeline Artifacts
Navigate to **Generated Artifacts** to inspect and download:
- Full Consolidated 4-Stage SQL (`.sql`)
- Production Apache Airflow DAG (`.py`)
- Dataproc PySpark Iceberg Migration Job (`.py`)
- Complete Snowflake dbt Project (`dbt_project.yml`, staging models, marts models, schema tests)
- Migration Audit Manifest (`.json`)
