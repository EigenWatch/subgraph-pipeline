import dagster as dg
import pandas as pd

from utils.debug_print import debug_print
from utils.query_builder import SubgraphQueryBuilder
from utils.subgraph_client import SubgraphClient


@dg.asset(group_name="extract_operator_events")
def extract_registration_events(
    context: dg.OpExecutionContext,
    query_builder: SubgraphQueryBuilder,
    subgraph_client: SubgraphClient,
) -> pd.DataFrame:
    """
    Extract the first 50 OperatorRegistered events from the subgraph using the SubgraphClient resource.
    """

    event_name = "operatorRegistereds"  # pluralized GraphQL entity name
    fields = [
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "delegationApprover",
    ]
    nested_fields = {"operator": ["id", "address"]}

    # Build query dynamically
    query = query_builder.build_query(
        event_name=event_name,
        fields=fields,
        first=50,
        order_by="blockNumber",
        order_direction="asc",
        nested_fields=nested_fields,
    )

    debug_print(query)
    context.log.info("Fetching registration events via SubgraphClient...")

    # Use the SubgraphClient resource
    try:
        response = subgraph_client.query(query)
    except Exception as e:
        context.log.error(f"Subgraph query failed: {e}")
        raise

    # Extract event data
    data = response.get("data", {}).get(event_name, [])
    if not data:
        context.log.warning("No registration events found.")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(data)
    context.log.info(f"Fetched {len(df)} registration events.")
    debug_print(df)
    return df
