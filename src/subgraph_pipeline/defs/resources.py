import dagster as dg

from utils.query_builder import SubgraphQueryBuilder


@dg.definitions
def resources():
    return dg.Definitions(
        resources={
            "SubgraphQueryBuilder": SubgraphQueryBuilder,
        }
    )
