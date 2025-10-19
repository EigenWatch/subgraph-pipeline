from typing import Optional, List, Dict


class SubgraphQueryBuilder:
    """
    Utility class for generating efficient GraphQL queries dynamically for subgraph event fetching.
    Follows The Graph best practices (id-based pagination, small batches, composable filters).
    """

    def __init__(self, event_name: str, fields: List[str]):
        """
        :param event_name: The individual entity name, e.g., 'OperatorRegisteredEvent'
        :param fields: List of field names to query from each event
        """
        self.event_name = event_name
        self.fields = fields

    def _build_where_clause(self, **filters: Dict[str, any]) -> str:
        """
        Internal utility to convert Python filters into GraphQL 'where' clause syntax.
        Automatically quotes strings and joins filters with commas.
        """
        if not filters:
            return ""

        parts = []
        for k, v in filters.items():
            if v is None:
                continue
            # Automatically wrap strings in quotes
            value = f'"{v}"' if isinstance(v, str) else v
            parts.append(f"{k}: {value}")

        if not parts:
            return ""
        return f"(where: {{{', '.join(parts)}}})"

    def build_query(
        self,
        first: int = 200,
        last_id: Optional[str] = None,
        block_number_gte: Optional[int] = None,
        block_number_lt: Optional[int] = None,
        order_by: str = "id",
        order_direction: str = "asc",
        extra_filters: Optional[Dict[str, any]] = None,
    ) -> str:
        """
        Build a GraphQL query for this event type using id-based pagination.
        Supports block range and custom filters.

        :param first: Number of records to fetch (recommended <= 200)
        :param last_id: For id-based pagination, use 'id_gt: last_id'
        :param block_number_gte: Minimum block number
        :param block_number_lt: Maximum block number
        :param extra_filters: Additional where filters (dict)
        """

        filters = {}

        # Add id-based pagination
        if last_id:
            filters["id_gt"] = last_id

        # Add block range filters
        if block_number_gte is not None:
            filters["blockNumber_gte"] = block_number_gte
        if block_number_lt is not None:
            filters["blockNumber_lt"] = block_number_lt

        # Merge in user-defined filters
        if extra_filters:
            filters.update(extra_filters)

        where_clause = self._build_where_clause(**filters)

        fields_block = "\n        ".join(self.fields)

        query = f"""
        query {{
          {self.event_name}(
            first: {first},
            orderBy: {order_by},
            orderDirection: {order_direction}
            {where_clause}
          ) {{
            {fields_block}
          }}
        }}
        """
        return query.strip()

    def build_block_range_queries(
        self,
        block_ranges: List[Dict[str, int]],
        first: int = 200,
        **kwargs,
    ) -> List[str]:
        """
        Generate multiple queries for given block ranges.
        Useful when batching large datasets safely within query limits.

        :param block_ranges: List of dicts, e.g. [{'gte': 1000, 'lt': 2000}, ...]
        :param first: Items per query (default 200)
        """
        queries = []
        for r in block_ranges:
            q = self.build_query(
                first=first,
                block_number_gte=r.get("gte"),
                block_number_lt=r.get("lt"),
                **kwargs,
            )
            queries.append(q)
        return queries
