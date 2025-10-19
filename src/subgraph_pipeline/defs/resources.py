import dagster as dg

from utils.query_builder import SubgraphQueryBuilder
from utils.subgraph_client import SubgraphClient


@dg.definitions
def resources():
    return dg.Definitions(
        resources={
            "query_builder": SubgraphQueryBuilder(),
            "subgraph_client": SubgraphClient(
                endpoint=dg.EnvVar("SUBGRAPH_ENDPOINT"),
                api_key=dg.EnvVar("SUBGRAPH_API_KEY"),
            ),
        }
    )
