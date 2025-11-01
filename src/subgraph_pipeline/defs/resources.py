import dagster as dg

from database.database_client import DatabaseClient
from database.entity_manager import EntityManager
from database.event_loader import EventLoader
from utils.event_transformers import EventTransformer
from utils.query_builder import SubgraphQueryBuilder
from utils.subgraph_client import SubgraphClient

all_operator_events_job = dg.define_asset_job(
    name="all_operator_events",
    selection="*",
    description="Process all operator events sequentially",
)

# Schedule to run 4 times a day at equal intervals (every 6 hours)
# Runs at: 00:00, 06:00, 12:00, 18:00 UTC
operator_events_schedule = dg.ScheduleDefinition(
    job=all_operator_events_job,
    cron_schedule="0 0,6,12,18 * * *",  # At minute 0 of hours 0, 6, 12, and 18
    name="operator_events_4x_daily",
    description="Run operator event extraction 4 times daily at 6-hour intervals",
)


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
        },
        jobs=[all_operator_events_job],
        schedules=[operator_events_schedule],
    )
