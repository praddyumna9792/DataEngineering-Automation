"""
Mock Catalog containing deterministic metadata for BigQuery and Snowflake.
Used in Simulation Mode without needing live cloud credentials.
"""
from typing import Dict, List, Optional
from core.models import TableMetadata, ColumnMetadata


class MockCatalog:
    """Provides deterministic metadata for simulation testing."""

    @staticmethod
    def get_bigquery_tables() -> List[TableMetadata]:
        return [
            # 1. Customer History (Partitioned, exists in SF with compatible schema)
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.legacy_dw.customer_history",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="legacy_dw",
                table_name="customer_history",
                columns=[
                    ColumnMetadata(name="customer_id", data_type="INT64", is_nullable=False, is_primary_key=True, comment="Primary key"),
                    ColumnMetadata(name="signup_date", data_type="DATE", is_nullable=False, is_partition_col=True, comment="Registration date"),
                    ColumnMetadata(name="email", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="first_name", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="last_name", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="country_code", data_type="STRING", is_nullable=True, is_clustering_col=True),
                    ColumnMetadata(name="account_balance", data_type="NUMERIC", precision=38, scale=9, is_nullable=False),
                    ColumnMetadata(name="loyalty_tier", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="is_active", data_type="BOOL", is_nullable=False),
                    ColumnMetadata(name="last_login_at", data_type="TIMESTAMP", is_nullable=True),
                    ColumnMetadata(name="preferences", data_type="JSON", is_nullable=True),
                ],
                row_count=1_250_000,
                size_bytes=480_000_000,
                partition_field="signup_date",
                partition_type="DAY",
                clustering_fields=["country_code"],
                location="US",
                description="Core customer registration and lifecycle historical dataset",
            ),

            # 2. Orders Archive (Partitioned, does NOT exist in Snowflake)
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.legacy_dw.orders_archive",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="legacy_dw",
                table_name="orders_archive",
                columns=[
                    ColumnMetadata(name="order_id", data_type="INT64", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="order_date", data_type="DATE", is_nullable=False, is_partition_col=True),
                    ColumnMetadata(name="customer_id", data_type="INT64", is_nullable=False),
                    ColumnMetadata(name="order_status", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="total_amount", data_type="NUMERIC", precision=38, scale=9, is_nullable=False),
                    ColumnMetadata(name="tax_amount", data_type="NUMERIC", precision=38, scale=9, is_nullable=True),
                    ColumnMetadata(name="discount_applied", data_type="NUMERIC", precision=38, scale=9, is_nullable=True),
                    ColumnMetadata(name="payment_method", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="created_at", data_type="TIMESTAMP", is_nullable=False),
                    ColumnMetadata(name="updated_at", data_type="TIMESTAMP", is_nullable=False),
                ],
                row_count=5_400_000,
                size_bytes=1_850_000_000,
                partition_field="order_date",
                partition_type="DAY",
                clustering_fields=["customer_id"],
                location="US",
                description="E-commerce historical archived sales transactions",
            ),

            # 3. Ambiguous Source Table: Match 1 in finance_raw
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.finance_raw.legacy_transactions",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="finance_raw",
                table_name="legacy_transactions",
                columns=[
                    ColumnMetadata(name="tx_id", data_type="STRING", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="tx_date", data_type="DATE", is_nullable=False, is_partition_col=True),
                    ColumnMetadata(name="amount", data_type="NUMERIC", precision=38, scale=2, is_nullable=False),
                    ColumnMetadata(name="currency", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="merchant_id", data_type="STRING", is_nullable=False),
                ],
                row_count=3_100_000,
                size_bytes=920_000_000,
                partition_field="tx_date",
                partition_type="DAY",
                clustering_fields=["merchant_id"],
                location="US",
                description="Financial ledger transactions from primary ERP",
            ),

            # 3. Ambiguous Source Table: Match 2 in archive_vault
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.archive_vault.legacy_transactions",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="archive_vault",
                table_name="legacy_transactions",
                columns=[
                    ColumnMetadata(name="tx_id", data_type="STRING", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="tx_timestamp", data_type="TIMESTAMP", is_nullable=False),
                    ColumnMetadata(name="amount", data_type="NUMERIC", precision=38, scale=2, is_nullable=False),
                    ColumnMetadata(name="notes", data_type="STRING", is_nullable=True),
                ],
                row_count=850_000,
                size_bytes=240_000_000,
                partition_field=None,
                partition_type=None,
                clustering_fields=[],
                location="US",
                description="Cold archived legacy payment logs",
            ),

            # 4. Employee Records (Has schema conflict with existing Snowflake target)
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.hr_legacy.employee_records",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="hr_legacy",
                table_name="employee_records",
                columns=[
                    ColumnMetadata(name="emp_id", data_type="INT64", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="emp_code", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="department", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="hire_date", data_type="DATE", is_nullable=False),
                    ColumnMetadata(name="salary", data_type="NUMERIC", precision=18, scale=2, is_nullable=False),
                ],
                row_count=45_000,
                size_bytes=15_000_000,
                partition_field=None,
                partition_type=None,
                clustering_fields=[],
                location="US",
                description="Historical human resource and payroll records",
            ),

            # 5. Clickstream Logs (High-volume dataset, used for batch recovery testing)
            TableMetadata(
                fully_qualified_id="acme-analytics-prod.telemetry.clickstream_logs",
                project_or_db="acme-analytics-prod",
                dataset_or_schema="telemetry",
                table_name="clickstream_logs",
                columns=[
                    ColumnMetadata(name="event_id", data_type="STRING", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="event_date", data_type="DATE", is_nullable=False, is_partition_col=True),
                    ColumnMetadata(name="session_id", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="user_pseudo_id", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="page_path", data_type="STRING", is_nullable=False),
                    ColumnMetadata(name="referrer", data_type="STRING", is_nullable=True),
                    ColumnMetadata(name="event_timestamp", data_type="TIMESTAMP", is_nullable=False),
                ],
                row_count=12_000_000,
                size_bytes=6_500_000_000,
                partition_field="event_date",
                partition_type="DAY",
                clustering_fields=["session_id"],
                location="US",
                description="High velocity web and mobile user interaction logs",
            ),
        ]

    @staticmethod
    def get_snowflake_tables() -> List[TableMetadata]:
        return [
            # 1. CUSTOMER_HISTORY (Target exists and is COMPATIBLE)
            TableMetadata(
                fully_qualified_id="ANALYTICS_DW.HISTORICAL.CUSTOMER_HISTORY",
                project_or_db="ANALYTICS_DW",
                dataset_or_schema="HISTORICAL",
                table_name="CUSTOMER_HISTORY",
                columns=[
                    ColumnMetadata(name="CUSTOMER_ID", data_type="NUMBER(38,0)", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="SIGNUP_DATE", data_type="DATE", is_nullable=False),
                    ColumnMetadata(name="EMAIL", data_type="VARCHAR(255)", is_nullable=False),
                    ColumnMetadata(name="FIRST_NAME", data_type="VARCHAR(100)", is_nullable=True),
                    ColumnMetadata(name="LAST_NAME", data_type="VARCHAR(100)", is_nullable=True),
                    ColumnMetadata(name="COUNTRY_CODE", data_type="VARCHAR(10)", is_nullable=True),
                    ColumnMetadata(name="ACCOUNT_BALANCE", data_type="NUMBER(38,9)", is_nullable=False),
                    ColumnMetadata(name="LOYALTY_TIER", data_type="VARCHAR(50)", is_nullable=True),
                    ColumnMetadata(name="IS_ACTIVE", data_type="BOOLEAN", is_nullable=False),
                    ColumnMetadata(name="LAST_LOGIN_AT", data_type="TIMESTAMP_NTZ", is_nullable=True),
                    ColumnMetadata(name="PREFERENCES", data_type="VARIANT", is_nullable=True),
                ],
                row_count=0,
                size_bytes=0,
                description="Existing Snowflake target table for customer history",
            ),

            # 2. EMPLOYEE_RECORDS (Target exists but is INCOMPATIBLE: EMP_ID is VARCHAR, department missing)
            TableMetadata(
                fully_qualified_id="ANALYTICS_DW.HISTORICAL.EMPLOYEE_RECORDS",
                project_or_db="ANALYTICS_DW",
                dataset_or_schema="HISTORICAL",
                table_name="EMPLOYEE_RECORDS",
                columns=[
                    # Mismatched type: EMP_ID is VARCHAR(20) in Snowflake vs INT64 in BigQuery
                    ColumnMetadata(name="EMP_ID", data_type="VARCHAR(20)", is_nullable=False, is_primary_key=True),
                    ColumnMetadata(name="EMP_CODE", data_type="VARCHAR(50)", is_nullable=False),
                    # Missing 'DEPARTMENT' column
                    ColumnMetadata(name="HIRE_DATE", data_type="DATE", is_nullable=False),
                    # Extra column in target not in source
                    ColumnMetadata(name="LEGACY_COST_CENTER", data_type="VARCHAR(30)", is_nullable=True),
                    ColumnMetadata(name="SALARY", data_type="NUMBER(18,2)", is_nullable=False),
                ],
                row_count=100,
                size_bytes=10000,
                description="Legacy HR table with incompatible structure",
            ),
        ]
