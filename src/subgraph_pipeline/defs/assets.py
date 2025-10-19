from typing import List, Dict, Optional
import dagster as dg
import pandas as pd

from utils.debug_print import debug_print
from utils.query_builder import SubgraphQueryBuilder
from utils.subgraph_client import SubgraphClient


def create_event_extraction_asset(
    event_name: str,
    fields: List[str],
    nested_fields: Optional[Dict[str, List[str]]] = None,
    first: int = 50,
    order_by: str = "blockNumber",
    order_direction: str = "asc",
    group_name: str = "extract_events",
) -> dg.AssetsDefinition:
    """
    Factory function to create event extraction assets dynamically.
    """

    @dg.asset(
        name=f"extract_{event_name}",
        group_name=group_name,
        metadata={
            "event_type": event_name,
            "fields": fields,
        },
    )
    def _extract_event(
        context: dg.OpExecutionContext,
        query_builder: SubgraphQueryBuilder,
        subgraph_client: SubgraphClient,
    ) -> pd.DataFrame:
        """Extract {event_name} events from the subgraph."""

        query = query_builder.build_query(
            event_name=event_name,
            fields=fields,
            first=first,
            order_by=order_by,
            order_direction=order_direction,
            nested_fields=nested_fields,
        )

        debug_print(query)
        context.log.info(f"Fetching {event_name} via SubgraphClient...")

        try:
            response = subgraph_client.query(query)
        except Exception as e:
            context.log.error(f"Subgraph query failed: {e}")
            raise

        data = response.get("data", {}).get(event_name, [])
        if not data:
            context.log.warning(f"No {event_name} found.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        context.log.info(f"Fetched {len(df)} {event_name}.")
        debug_print(df)
        return df

    return _extract_event


# Define your assets
extract_registration_events = create_event_extraction_asset(
    event_name="operatorRegistereds",
    fields=[
        "id",
        "transactionHash",
        "blockNumber",
        "blockTimestamp",
        "contractAddress",
        "operator",
        "delegationApprover",
    ],
    nested_fields={"operator": ["id", "address"]},
    group_name="extract_operator_events",
)
