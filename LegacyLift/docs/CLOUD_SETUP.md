# LegacyLift Cloud Setup & Live Execution Guide

This document provides step-by-step instructions for transitioning LegacyLift from **SIMULATION** mode to **LIVE** execution against real Google Cloud and Snowflake enterprise environments.

---

## 1. Google Cloud Platform (GCP) Configuration

### 1.1 Enable Required Cloud APIs
Run the following in Cloud Shell or via the `gcloud` CLI:
```bash
gcloud services enable \
    bigquery.googleapis.com \
    storage.googleapis.com \
    dataproc.googleapis.com \
    biglake.googleapis.com
```

### 1.2 Service Account & IAM Roles
Create a dedicated service account for LegacyLift:
```bash
gcloud iam service-accounts create legacylift-migrator \
    --description="LegacyLift Historical Data Migrator" \
    --display-name="LegacyLift-Migrator"

# Grant BigQuery Admin access
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:legacylift-migrator@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.admin"

# Grant Google Cloud Storage Admin access for staging Iceberg files
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:legacylift-migrator@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Download key
gcloud iam service-accounts keys create legacylift-sa-key.json \
    --iam-account="legacylift-migrator@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

### 1.3 Create Staging GCS Bucket
```bash
gsutil mb -l US -b on gs://legacylift-iceberg-prod-us/
```

---

## 2. Snowflake Integration & GCS Trust Setup

### 2.1 Create Snowflake Storage Integration
Run this SQL in Snowflake as `ACCOUNTADMIN`:
```sql
CREATE STORAGE INTEGRATION IF NOT EXISTS GCS_LEGACYLIFT_STORAGE_INT
    TYPE = EXTERNAL_STAGE
    STORAGE_PROVIDER = 'GCS'
    ENABLED = TRUE
    STORAGE_ALLOWED_LOCATIONS = ('gs://legacylift-iceberg-prod-us/iceberg/');

DESC STORAGE INTEGRATION GCS_LEGACYLIFT_STORAGE_INT;
```
*Note the value of `STORAGE_GCP_SERVICE_ACCOUNT` from the command output (e.g. `xyz@gcp-snowflake-integration.iam.gserviceaccount.com`).*

### 2.2 Grant Storage Permissions to Snowflake in GCS
Grant the Snowflake service account access to your staging bucket:
```bash
gsutil iam ch \
    serviceAccount:xyz@gcp-snowflake-integration.iam.gserviceaccount.com:roles/storage.objectViewer \
    gs://legacylift-iceberg-prod-us
```

### 2.3 Create External Volume for Iceberg
```sql
CREATE EXTERNAL VOLUME IF NOT EXISTS EXVOL_LEGACYLIFT_ICEBERG
    STORAGE_LOCATIONS = (
        (
            NAME = 'gcs-iceberg-prod'
            STORAGE_PROVIDER = 'GCS'
            STORAGE_BASE_URL = 'gs://legacylift-iceberg-prod-us/iceberg/'
        )
    )
    COMMENT = 'LegacyLift external volume pointing to historical Iceberg files';
```

---

## 3. Transitioning from Simulation to Live Mode in LegacyLift

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Update the credentials in `.env`:
   ```ini
   LEGACYLIFT_MODE=LIVE
   GCP_PROJECT_ID=your-actual-gcp-project
   GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/legacylift-sa-key.json
   GCS_BUCKET=gs://legacylift-iceberg-prod-us
   SNOWFLAKE_ACCOUNT=your_org-your_account
   SNOWFLAKE_USER=MIGRATION_ADMIN
   SNOWFLAKE_PASSWORD=your_secure_password
   SNOWFLAKE_WAREHOUSE=COMPUTE_WH
   SNOWFLAKE_DATABASE=ANALYTICS_DW
   SNOWFLAKE_SCHEMA=HISTORICAL
   ```
3. Install live cloud Python drivers:
   ```bash
   pip install google-cloud-bigquery google-cloud-storage snowflake-connector-python
   ```
4. Start the application:
   ```bash
   run_app.bat   # Windows
   ./run_app.sh  # Unix
   ```
5. Open **Settings** in the application and click:
   - **Test BigQuery Access**
   - **Test Snowflake Access**
   - **Test GCS Bucket Access**
6. Once all checks pass, you are ready to execute live historical migrations!
