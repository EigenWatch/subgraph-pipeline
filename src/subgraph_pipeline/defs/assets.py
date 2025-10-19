import dagster as dg


@dg.asset
def raw_subgraph_events() -> str:
    return "This is a placeholder asset."
