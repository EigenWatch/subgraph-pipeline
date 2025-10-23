import dagster as dg

from database.database_client import DatabaseClient
from database.entity_manager import EntityManager
from database.event_loader import EventLoader
from utils.event_transformers import EventTransformer
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
            "db_client": DatabaseClient(
                connection_string=dg.EnvVar("POSTGRES_CONNECTION_STRING"),
                pool_size=5,
                max_overflow=10,
            ),
            "entity_manager": EntityManager(),
            "event_loader": EventLoader(),
            "transformer": EventTransformer(),
        }
    )
