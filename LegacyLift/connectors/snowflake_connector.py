"""
Snowflake Connector implementation supporting Simulation and Live Cloud modes.
"""
from typing import List, Optional, Dict, Any
from connectors.base import BaseSnowflakeConnector
from core.models import TableMetadata, TargetTableStatus, ColumnMetadata
from simulation.mock_catalog import MockCatalog
from config.settings import current_config


class SnowflakeConnector(BaseSnowflakeConnector):
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or current_config.execution.mode

    def search_tables(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        clean_name = table_name.strip().upper()
        if not clean_name:
            return []

        if self.mode == "SIMULATION":
            tables = MockCatalog.get_snowflake_tables()
            matches = []
            for t in tables:
                if t.table_name.upper() == clean_name:
                    if search_scope:
                        if search_scope.upper() in t.fully_qualified_id.upper():
                            matches.append(t)
                    else:
                        matches.append(t)
            return matches

        return self._search_tables_live(clean_name, search_scope)

    def get_table_metadata(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        if self.mode == "SIMULATION":
            tables = MockCatalog.get_snowflake_tables()
            for t in tables:
                if t.fully_qualified_id.upper() == fully_qualified_id.upper():
                    return t
            return None

        return self._get_table_metadata_live(fully_qualified_id)

    def check_table_exists(self, fully_qualified_id_or_name: str) -> TargetTableStatus:
        clean = fully_qualified_id_or_name.strip().upper()
        # If it's a short name, search
        if "." not in clean:
            matches = self.search_tables(clean)
            if len(matches) > 1:
                return TargetTableStatus.AMBIGUOUS
            elif len(matches) == 1:
                return TargetTableStatus.EXISTS
            else:
                return TargetTableStatus.NOT_FOUND

        # Fully qualified ID check
        meta = self.get_table_metadata(clean)
        if meta:
            return TargetTableStatus.EXISTS
        return TargetTableStatus.NOT_FOUND

    def test_connection(self) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "message": "Connected to Snowflake Simulation Catalog (ANALYTICS_DW.HISTORICAL)",
                "warehouse": current_config.snowflake.warehouse,
                "role": current_config.snowflake.role,
                "database": current_config.snowflake.default_database,
                "schema": current_config.snowflake.default_schema,
                "external_volume": current_config.snowflake.external_volume,
                "storage_integration": current_config.snowflake.storage_integration,
            }

        try:
            import snowflake.connector
            ctx = snowflake.connector.connect(
                user=current_config.snowflake.user,
                password=current_config.snowflake.password,
                account=current_config.snowflake.account,
                warehouse=current_config.snowflake.warehouse,
                database=current_config.snowflake.default_database,
                schema=current_config.snowflake.default_schema,
                role=current_config.snowflake.role,
            )
            cs = ctx.cursor()
            cs.execute("SELECT CURRENT_VERSION(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            row = cs.fetchone()
            cs.close()
            ctx.close()
            return {
                "success": True,
                "mode": "LIVE",
                "message": f"Successfully connected to Snowflake. Version: {row[0]}",
                "warehouse": row[1],
                "database": row[2],
                "schema": row[3],
            }
        except ImportError:
            return {
                "success": False,
                "mode": "LIVE",
                "message": "snowflake-connector-python library is not installed.",
                "remediation": "Install via `pip install snowflake-connector-python`.",
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "message": f"Snowflake live connection failed: {str(e)}",
                "remediation": "Check account, credentials, and network access policy.",
            }

    def execute_query(self, query: str) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "query": query,
                "rows_affected": 0,
                "message": "Simulated query executed successfully.",
            }

        try:
            import snowflake.connector
            ctx = snowflake.connector.connect(
                user=current_config.snowflake.user,
                password=current_config.snowflake.password,
                account=current_config.snowflake.account,
                warehouse=current_config.snowflake.warehouse,
                database=current_config.snowflake.default_database,
                schema=current_config.snowflake.default_schema,
                role=current_config.snowflake.role,
            )
            cs = ctx.cursor()
            cs.execute(query)
            rowcount = cs.rowcount
            cs.close()
            ctx.close()
            return {
                "success": True,
                "mode": "LIVE",
                "query": query,
                "rows_affected": rowcount,
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "error": str(e),
            }

    def _search_tables_live(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        try:
            import snowflake.connector
            ctx = snowflake.connector.connect(
                user=current_config.snowflake.user,
                password=current_config.snowflake.password,
                account=current_config.snowflake.account,
                warehouse=current_config.snowflake.warehouse,
                database=current_config.snowflake.default_database,
                schema=current_config.snowflake.default_schema,
                role=current_config.snowflake.role,
            )
            cs = ctx.cursor()
            query = f"SHOW TABLES LIKE '{table_name}' IN ACCOUNT"
            cs.execute(query)
            rows = cs.fetchall()
            matched = []
            for r in rows:
                db = r[1]
                schema = r[2]
                name = r[3]
                fqn = f"{db}.{schema}.{name}"
                meta = self.get_table_metadata(fqn)
                if meta:
                    matched.append(meta)
            cs.close()
            ctx.close()
            return matched
        except Exception:
            return []

    def _get_table_metadata_live(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        try:
            import snowflake.connector
            ctx = snowflake.connector.connect(
                user=current_config.snowflake.user,
                password=current_config.snowflake.password,
                account=current_config.snowflake.account,
                warehouse=current_config.snowflake.warehouse,
                database=current_config.snowflake.default_database,
                schema=current_config.snowflake.default_schema,
                role=current_config.snowflake.role,
            )
            cs = ctx.cursor()
            cs.execute(f"DESCRIBE TABLE {fully_qualified_id}")
            cols_data = cs.fetchall()
            columns = [
                ColumnMetadata(
                    name=c[0],
                    data_type=c[1],
                    is_nullable=(c[3] == "Y"),
                    is_primary_key=(c[5] == "Y"),
                    comment=c[9] if len(c) > 9 else None,
                )
                for c in cols_data
            ]
            parts = fully_qualified_id.split(".")
            cs.close()
            ctx.close()
            return TableMetadata(
                fully_qualified_id=fully_qualified_id,
                project_or_db=parts[0] if len(parts) > 0 else current_config.snowflake.default_database,
                dataset_or_schema=parts[1] if len(parts) > 1 else current_config.snowflake.default_schema,
                table_name=parts[2] if len(parts) > 2 else fully_qualified_id,
                columns=columns,
            )
        except Exception:
            return None
