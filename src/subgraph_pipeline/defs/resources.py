import dagster as dg

from utils.query_builder import SubgraphQueryBuilder


@dg.definitions
def resources():
    return dg.Definitions(
        resources={
            "query_builder": SubgraphQueryBuilder(),
            "subgraph_url": "https://api.studio.thegraph.com/query/116357/eigenwatch-ethereum/version/latest",
        }
    )
