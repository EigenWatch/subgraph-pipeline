import dagster as dg
import pandas as pd
import requests

from utils.debug_print import debug_print
from utils.query_builder import SubgraphQueryBuilder


@dg.asset(group_name="extract_operator_events")
def extract_registration_events(
    context: dg.OpExecutionContext, query_builder: SubgraphQueryBuilder
) -> pd.DataFrame:
    """
    Extract the first 50 OperatorRegistered events from the subgraph.
    """

    # Define the event and fields to pull from your subgraph schema
    event_name = "operatorRegistereds"  # note plural form for GraphQL entity
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

    # Build the GraphQL query dynamically
    query = query_builder.build_query(
        event_name=event_name,
        fields=fields,
        first=50,  # limit
        order_by="blockNumber",
        order_direction="asc",
        nested_fields=nested_fields,
    )

    debug_print(query)  # Debug print the generated query

    # The endpoint should be configured in Dagster resources/environment
    subgraph_url = (
        context.resources.subgraph_url
    )  # e.g. "https://api.thegraph.com/subgraphs/name/project/subgraph"

    # Execute query
    context.log.info(f"Fetching registration events from {subgraph_url}")
    response = requests.post(subgraph_url, json={"query": query})

    # Handle response
    if response.status_code != 200:
        raise Exception(
            f"GraphQL query failed: {response.status_code} - {response.text}"
        )

    data = response.json().get("data", {}).get(event_name, [])
    if not data:
        context.log.warning("No registration events found.")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(data)

    context.log.info(f"Fetched {len(df)} registration events.")
    return df
