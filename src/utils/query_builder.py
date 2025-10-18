from typing import Optional, List, Dict


class SubgraphQueryBuilder:
    """
    Utility class for generating GraphQL queries dynamically for subgraph event fetching.
    Designed for use in Dagster ETL pipelines.
    """

    def __init__(self, subgraph_name: str, event_name: str, fields: List[str]):
        """
        :param subgraph_name: The root query name, e.g., 'operatorRegisteredEvents'
        :param event_name: The individual entity name, e.g., 'OperatorRegisteredEvent'
        :param fields: List of field names to query from each event
        """
        self.subgraph_name = subgraph_name
        self.event_name = event_name
        self.fields = fields

    def build_query(
        self,
        first: int = 1000,
        skip: int = 0,
        block_number_gt: Optional[int] = None,
        block_number_lte: Optional[int] = None,
        order_by: str = "blockNumber",
        order_direction: str = "asc",
        filters: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build a GraphQL query for this event type.
        Supports pagination and block filtering.
        """

        # Build filter string
        filter_parts = []
        if block_number_gt is not None:
            filter_parts.append(f"blockNumber_gt: {block_number_gt}")
        if block_number_lte is not None:
            filter_parts.append(f"blockNumber_lte: {block_number_lte}")
        if filters:
            for k, v in filters.items():
                # Automatically quote string filters
                value = f'"{v}"' if isinstance(v, str) else v
                filter_parts.append(f"{k}: {value}")

        where_clause = ""
        if filter_parts:
            where_clause = f"(where: {{{', '.join(filter_parts)}}})"

        # Construct field block
        fields_block = "\n        ".join(self.fields)

        # Build query
        query = f"""
        query {{
          {self.subgraph_name}(
            first: {first},
            skip: {skip},
            orderBy: {order_by},
            orderDirection: {order_direction}
            {where_clause}
          ) {{
            {fields_block}
          }}
        }}
        """
        return query.strip()

    def paginated_queries(
        self,
        total_records: int,
        page_size: int = 1000,
        **kwargs,
    ) -> List[str]:
        """
        Generate a list of paginated queries for large datasets.
        """
        queries = []
        for skip in range(0, total_records, page_size):
            queries.append(self.build_query(first=page_size, skip=skip, **kwargs))
        return queries
