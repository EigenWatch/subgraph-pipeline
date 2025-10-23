"""
Event extraction and loading assets.
Combines extraction, transformation, entity upserts, and event loading.
"""

from typing import Dict, Any
import dagster as dg
import pandas as pd

from config.event_config import OPERATOR_EVENT_CONFIGS, EventConfig
from database.database_client import DatabaseClient
from database.entity_manager import EntityManager
from database.event_loader import EventLoader
from utils.event_transformers import EventTransformer
from utils.query_builder import SubgraphQueryBuilder
from utils.subgraph_client import SubgraphClient
from utils.debug_print import debug_print


def create_event_extraction_and_load_asset(
    config: EventConfig,
    first: int = 100,
    order_by: str = "blockNumber",
    order_direction: str = "asc",
) -> dg.AssetsDefinition:
    """
    Factory function to create event extraction + load assets.

    This creates a single asset that:
    1. Extracts events from subgraph
    2. Transforms data (flatten, type conversions)
    3. Upserts dependent entities (Operator, etc.)
    4. Loads events into database

    Args:
        config: EventConfig from event_registry
        first: Number of records to fetch per query
        order_by: Field to order results by
        order_direction: 'asc' or 'desc'

    Returns:
        Dagster AssetsDefinition
    """

    @dg.asset(
        name=f"load_{config['table_name']}",
        group_name=config["group_name"],
        metadata={
            "event_type": config["graphql_name"],
            "table": config["table_name"],
            "contract": config["contract_source"],
            "entities": config["entity_dependencies"],
        },
    )
    def _extract_and_load_event(
        context: dg.OpExecutionContext,
        query_builder: SubgraphQueryBuilder,
        subgraph_client: SubgraphClient,
        db_client: DatabaseClient,
        entity_manager: EntityManager,
        event_loader: EventLoader,
        transformer: EventTransformer,
    ) -> Dict[str, Any]:
        """
        Extract {config['graphql_name']} events and load to {config['table_name']}.
        """

        # ========================================
        # STEP 1: EXTRACT FROM SUBGRAPH
        # ========================================
        context.log.info(f"Extracting {config['graphql_name']} from subgraph...")

        # Check for last processed block for incremental loading
        with db_client.get_session() as session:
            last_block = event_loader.get_last_processed_block(
                session, config["table_name"]
            )

        # Build query with optional block filter
        block_number_gte = None
        if last_block is not None:
            block_number_gte = last_block
            context.log.info(f"Incremental load: starting from block {last_block + 1}")

        query = query_builder.build_query(
            event_name=config["graphql_name"],
            fields=config["fields"],
            first=first,
            order_by=order_by,
            order_direction=order_direction,
            nested_fields=config.get("nested_fields"),
            block_number_gte=block_number_gte,
        )

        debug_print(query)

        try:
            response = subgraph_client.query(query)
        except Exception as e:
            context.log.error(f"Subgraph query failed: {e}")
            raise

        # Extract event data
        data = response.get("data", {}).get(config["graphql_name"], [])
        if not data:
            context.log.warning(f"No new {config['graphql_name']} found.")
            return {
                "status": "no_new_data",
                "events_fetched": 0,
                "last_block": last_block,
            }

        df = pd.DataFrame(data)
        context.log.info(f"Fetched {len(df)} {config['graphql_name']} events.")
        debug_print(df.head())

        # ========================================
        # STEP 2: TRANSFORM DATA
        # ========================================
        context.log.info("Transforming event data...")

        df_transformed = transformer.transform_event_data(
            df=df,
            config=config,
            original_data=data,  # Keep original for raw_data column
        )

        # ========================================
        # STEP 3: UPSERT ENTITIES
        # ========================================
        context.log.info("Upserting dependent entities...")

        entity_stats = {}

        with db_client.get_session() as session:
            for entity_type in config["entity_dependencies"]:
                # Extract entity IDs using configured extractor
                extractor = config["entity_extractors"].get(entity_type)
                if not extractor:
                    context.log.warning(
                        f"No extractor defined for entity type: {entity_type}"
                    )
                    continue

                try:
                    entity_ids = extractor(df)

                    # Call appropriate upsert method
                    if entity_type == "Operator":
                        stats = entity_manager.upsert_operators(
                            session, entity_ids, context
                        )
                    elif entity_type == "Staker":
                        stats = entity_manager.upsert_stakers(
                            session, entity_ids, context
                        )
                    elif entity_type == "AVS":
                        stats = entity_manager.upsert_avs(session, entity_ids, context)
                    elif entity_type == "Strategy":
                        stats = entity_manager.upsert_strategies(
                            session, entity_ids, context
                        )
                    else:
                        context.log.warning(f"Unknown entity type: {entity_type}")
                        stats = {"inserted": 0, "updated": 0, "skipped": 0}

                    entity_stats[entity_type] = stats

                except Exception as e:
                    context.log.error(f"Failed to upsert {entity_type}: {e}")
                    entity_stats[entity_type] = {"error": str(e)}

        # ========================================
        # STEP 4: LOAD EVENTS
        # ========================================
        context.log.info(f"Loading events into {config['table_name']}...")

        with db_client.get_session() as session:
            try:
                load_stats = event_loader.load_events(
                    session=session,
                    df=df_transformed,
                    table_name=config["table_name"],
                    context=context,
                )
            except Exception as e:
                context.log.error(f"Failed to load events: {e}")
                raise

        # ========================================
        # STEP 5: RETURN METADATA
        # ========================================
        result = {
            "status": "success",
            "events_fetched": len(df),
            "events_inserted": load_stats["inserted"],
            "events_updated": load_stats["updated"],
            "events_skipped": load_stats["skipped"],
            "events_errors": load_stats["errors"],
            "entities_upserted": entity_stats,
            "last_block_processed": (
                df_transformed["block_number"].max()
                if not df_transformed.empty
                else last_block
            ),
        }

        context.log.info(f"Asset completed successfully: {result}")

        # Log to Dagster metadata for visibility in UI
        context.add_output_metadata(
            {
                "events_fetched": dg.MetadataValue.int(result["events_fetched"]),
                "events_inserted": dg.MetadataValue.int(result["events_inserted"]),
                "last_block": dg.MetadataValue.int(result["last_block_processed"]),
                "entities": dg.MetadataValue.json(result["entities_upserted"]),
            }
        )

        return result

    return _extract_and_load_event


# Generate all assets programmatically
def generate_all_operator_event_assets():
    """
    Generate all operator event assets from registry.
    Use this if you prefer programmatic generation over explicit definitions.
    """
    assets = []
    for event_name, config in OPERATOR_EVENT_CONFIGS.items():
        asset = create_event_extraction_and_load_asset(config=config, first=100)
        assets.append(asset)
    return assets


operator_event_assets = generate_all_operator_event_assets()
