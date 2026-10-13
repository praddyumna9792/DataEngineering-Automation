"""
Unit tests for Metadata Discovery and Ambiguity Resolution.
"""
import pytest
from core.metadata_discovery import MetadataDiscoveryService
from core.models import TargetTableStatus


@pytest.fixture
def discovery_service():
    return MetadataDiscoveryService()


def test_resolve_source_table_exact(discovery_service):
    status, matches, selected = discovery_service.resolve_source_table("customer_history")
    assert status == "FOUND"
    assert len(matches) == 1
    assert selected is not None
    assert selected.table_name == "customer_history"
    assert selected.row_count == 1_250_000
    assert selected.partition_field == "signup_date"


def test_resolve_source_table_ambiguous(discovery_service):
    # 'legacy_transactions' exists in both finance_raw and archive_vault
    status, matches, selected = discovery_service.resolve_source_table("legacy_transactions")
    assert status == "AMBIGUOUS"
    assert len(matches) == 2
    assert selected is None
    # Verify candidate FQNs
    fqns = [m.fully_qualified_id for m in matches]
    assert "acme-analytics-prod.finance_raw.legacy_transactions" in fqns
    assert "acme-analytics-prod.archive_vault.legacy_transactions" in fqns


def test_resolve_source_table_not_found(discovery_service):
    status, matches, selected = discovery_service.resolve_source_table("non_existent_table_xyz")
    assert status == "NOT_FOUND"
    assert len(matches) == 0
    assert selected is None


def test_resolve_target_table_exists(discovery_service):
    status, matches, selected, fqn = discovery_service.resolve_target_table("CUSTOMER_HISTORY")
    assert status == TargetTableStatus.EXISTS
    assert len(matches) == 1
    assert selected is not None
    assert "CUSTOMER_HISTORY" in fqn


def test_resolve_target_table_not_found(discovery_service):
    status, matches, selected, fqn = discovery_service.resolve_target_table("ORDERS_ARCHIVE")
    assert status == TargetTableStatus.NOT_FOUND
    assert len(matches) == 0
    assert selected is None
    # Must fallback to default database & schema
    assert "ANALYTICS_DW.HISTORICAL.ORDERS_ARCHIVE" in fqn
