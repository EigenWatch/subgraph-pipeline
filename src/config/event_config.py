"""
Event configuration registry.
Defines all event types and their extraction/transformation rules.
"""

from typing import TypedDict, List, Optional, Dict, Callable


class EventConfig(TypedDict):
    """Configuration for a single event type."""

    graphql_name: str  # Event name in subgraph (e.g., "operatorRegistereds")
    table_name: str  # Database table name
    fields: List[str]  # GraphQL fields to query
    nested_fields: Optional[Dict[str, List[str]]]  # Nested object fields
    entity_dependencies: List[str]  # Entity types this event depends on
    entity_extractors: Dict[str, Callable]  # How to extract entity IDs from DataFrame
    column_mapping: Dict[str, str]  # GraphQL field name -> DB column name
    group_name: str  # Dagster asset group
    contract_source: str  # Source contract for documentation


# ============================================================================
# DELEGATION MANAGER EVENTS
# ============================================================================

OPERATOR_REGISTERED_CONFIG: EventConfig = {
    "graphql_name": "operatorRegistereds",
    "table_name": "operator_registered_events",
    "fields": [
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "delegationApprover",
    ],
    "nested_fields": {"operator": ["id", "address"]},
    "entity_dependencies": ["Operator"],
    "entity_extractors": {
        "Operator": lambda df: df["operator"]
        .apply(lambda x: x["id"] if isinstance(x, dict) else x)
        .unique()
        .tolist()
    },
    "column_mapping": {
        "transactionHash": "transaction_hash",
        "blockNumber": "block_number",
        "blockTimestamp": "block_timestamp",
        "contractAddress": "contract_address",
        "delegationApprover": "delegation_approver",
        "operator_id": "operator_id",  # After flattening
    },
    "group_name": "delegation_manager_events",
    "contract_source": "DelegationManager",
}

OPERATOR_METADATA_UPDATE_CONFIG: EventConfig = {
    "graphql_name": "operatorMetadataURIUpdateds",
    "table_name": "operator_metadata_update_events",
    "fields": [
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "metadataURI",
    ],
    "nested_fields": {"operator": ["id", "address"]},
    "entity_dependencies": ["Operator"],
    "entity_extractors": {
        "Operator": lambda df: df["operator"]
        .apply(lambda x: x["id"] if isinstance(x, dict) else x)
        .unique()
        .tolist()
    },
    "column_mapping": {
        "transactionHash": "transaction_hash",
        "blockNumber": "block_number",
        "blockTimestamp": "block_timestamp",
        "contractAddress": "contract_address",
        "metadataURI": "metadata_uri",
        "operator_id": "operator_id",
    },
    "group_name": "delegation_manager_events",
    "contract_source": "DelegationManager",
}

DELEGATION_APPROVER_UPDATED_CONFIG: EventConfig = {
    "graphql_name": "delegationApproverUpdateds",
    "table_name": "delegation_approver_updated_events",
    "fields": [
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "newDelegationApprover",
    ],
    "nested_fields": {"operator": ["id", "address"]},
    "entity_dependencies": ["Operator"],
    "entity_extractors": {
        "Operator": lambda df: df["operator"]
        .apply(lambda x: x["id"] if isinstance(x, dict) else x)
        .unique()
        .tolist()
    },
    "column_mapping": {
        "transactionHash": "transaction_hash",
        "blockNumber": "block_number",
        "blockTimestamp": "block_timestamp",
        "contractAddress": "contract_address",
        "newDelegationApprover": "new_delegation_approver",
        "operator_id": "operator_id",
    },
    "group_name": "delegation_manager_events",
    "contract_source": "DelegationManager",
}


# ============================================================================
# ALLOCATION MANAGER EVENTS
# ============================================================================

ALLOCATION_DELAY_SET_CONFIG: EventConfig = {
    "graphql_name": "allocationDelaysSets",
    "table_name": "allocation_delay_set_events",
    "fields": [
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "delay",
        "effectBlock",
    ],
    "nested_fields": {"operator": ["id", "address"]},
    "entity_dependencies": ["Operator"],
    "entity_extractors": {
        "Operator": lambda df: df["operator"]
        .apply(lambda x: x["id"] if isinstance(x, dict) else x)
        .unique()
        .tolist()
    },
    "column_mapping": {
        "transactionHash": "transaction_hash",
        "blockNumber": "block_number",
        "blockTimestamp": "block_timestamp",
        "contractAddress": "contract_address",
        "effectBlock": "effect_block",
        "operator_id": "operator_id",
    },
    "group_name": "allocation_manager_events",
    "contract_source": "AllocationManager",
}

# Note: For now, we'll define a minimal set of operator events
# You can expand this as needed for other events

# ============================================================================
# REGISTRY: All Operator Events
# ============================================================================

OPERATOR_EVENT_CONFIGS = {
    "operatorRegistereds": OPERATOR_REGISTERED_CONFIG,
    "operatorMetadataURIUpdateds": OPERATOR_METADATA_UPDATE_CONFIG,
    "delegationApproverUpdateds": DELEGATION_APPROVER_UPDATED_CONFIG,
    "allocationDelaysSets": ALLOCATION_DELAY_SET_CONFIG,
    # Add more as you implement them:
    # "operatorSlasheds": OPERATOR_SLASHED_CONFIG,
    # "allocationUpdateds": ALLOCATION_EVENT_CONFIG,
    # etc.
}


def get_event_config(graphql_name: str) -> EventConfig:
    """Get event configuration by GraphQL name."""
    if graphql_name not in OPERATOR_EVENT_CONFIGS:
        raise ValueError(f"Unknown event type: {graphql_name}")
    return OPERATOR_EVENT_CONFIGS[graphql_name]


def list_operator_events() -> List[str]:
    """List all configured operator event types."""
    return list(OPERATOR_EVENT_CONFIGS.keys())
