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


def create_event_extraction_and_load_assets(
    config: EventConfig,
    first: int = 100,
    order_by: str = "blockNumber",
    order_direction: str = "asc",
) -> list[dg.AssetsDefinition]:
    """
    Factory function to create event extraction + load assets.

    This creates multiple assets that:
    1. Extract events from subgraph
    2. Transform data (flatten, type conversions)
    3. Upsert dependent entities (Operator, etc.)
    4. Load events into database

    Args:
        config: EventConfig from event_registry
        first: Number of records to fetch per query
        order_by: Field to order results by
        order_direction: 'asc' or 'desc'

    Returns:
        List of Dagster AssetsDefinition
    """

    # Define asset names for dependency resolution
    extract_asset_name = f"extract_{config['table_name']}"
    transform_asset_name = f"transform_{config['table_name']}"
    upsert_asset_name = f"upsert_entities_{config['table_name']}"
    load_asset_name = f"load_{config['table_name']}"

    @dg.asset(
        name=extract_asset_name,
        group_name=config["group_name"],
    )
    def _extract_event(
        context: dg.OpExecutionContext,
        query_builder: SubgraphQueryBuilder,
        subgraph_client: SubgraphClient,
        db_client: DatabaseClient,
        event_loader: EventLoader,
    ) -> Dict[str, Any] | None:
        """
        Extract {config['graphql_name']} events from subgraph.
        """

        # ========================================
        # STEP 1: EXTRACT FROM SUBGRAPH
        # ========================================
        context.log.info(f"Extracting {config['graphql_name']} from subgraph...")

        # Check for last processed block for incremental loading
        with db_client.get_session() as session:
            # Get last cursor from DB (blockNumber + logIndex)
            last_cursor = event_loader.get_last_cursor(session, config["table_name"])

        # Default values
        cursor = None
        block_number_gte = None

        # Prefer cursor-based pagination if available
        if last_cursor:
            block_number, log_index = last_cursor
            cursor = {
                "blockNumber": block_number,
                "logIndex": log_index or 0,  # fallback to 0 if missing
            }
            context.log.info(
                f"Incremental load using cursor: block {cursor['blockNumber']}, logIndex {cursor['logIndex']}"
            )
        else:
            # Fallback: start from next block after last processed
            with db_client.get_session() as session:
                last_block = event_loader.get_last_processed_block(
                    session, config["table_name"]
                )
            if last_block is not None:
                block_number_gte = last_block + 1
                context.log.info(
                    f"Incremental load: starting from block {block_number_gte}"
                )
            else:
                context.log.info(
                    "No previous cursor or block found — full load will run."
                )

        # ✅ Build query dynamically
        query = query_builder.build_query(
            event_name=config["graphql_name"],
            fields=config["fields"],
            first=first,
            order_by=order_by,
            order_direction=order_direction,
            nested_fields=config.get("nested_fields"),
            cursor=cursor if cursor else None,
            block_number_gte=(
                None
                if cursor
                else (block_number_gte if last_block is not None else None)
            ),
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
            return None

        df = pd.DataFrame(data)
        context.log.info(f"Fetched {len(df)} {config['graphql_name']} events.")
        debug_print(df.head())

        return {"df": df, "data": data}

    @dg.asset(
        name=transform_asset_name,
        group_name=config["group_name"],
        ins={
            "extract_output": dg.AssetIn(key=extract_asset_name),
        },
    )
    def _transform_event(
        context: dg.OpExecutionContext,
        extract_output: Dict[str, Any] | None,
        transformer: EventTransformer,
    ) -> pd.DataFrame | None:
        """
        Transform extracted {config['graphql_name']} event data.
        """

        if extract_output is None:
            return None

        # ========================================
        # STEP 2: TRANSFORM DATA
        # ========================================
        context.log.info("Transforming event data...")

        df = extract_output["df"]
        data = extract_output["data"]

        df_transformed = transformer.transform_event_data(
            df=df,
            config=config,
            original_data=data,  # Keep original for raw_data column
        )

        return df_transformed

    @dg.asset(
        name=upsert_asset_name,
        group_name=config["group_name"],
        ins={
            "transform_output": dg.AssetIn(key=transform_asset_name),
        },
    )
    def _upsert_entities(
        context: dg.OpExecutionContext,
        transform_output: pd.DataFrame | None,
        db_client: DatabaseClient,
        entity_manager: EntityManager,
    ) -> Dict[str, Any]:
        """
        Upsert entities for {config['graphql_name']} events.
        """

        if transform_output is None:
            return {}

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
                    entity_ids = extractor(transform_output)

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

        return entity_stats

    @dg.asset(
        name=load_asset_name,
        group_name=config["group_name"],
        metadata={
            "event_type": config["graphql_name"],
            "table": config["table_name"],
            "contract": config["contract_source"],
            "entities": config["entity_dependencies"],
        },
        ins={
            "transform_output": dg.AssetIn(key=transform_asset_name),
            "upsert_output": dg.AssetIn(key=upsert_asset_name),
        },
    )
    def _load_event(
        context: dg.OpExecutionContext,
        transform_output: pd.DataFrame | None,
        upsert_output: Dict[str, Any],
        db_client: DatabaseClient,
        event_loader: EventLoader,
    ) -> Dict[str, Any]:
        """
        Load transformed {config['graphql_name']} events into {config['table_name']}.
        """

        if transform_output is None:
            context.log.info(f"No new data to load into {config['table_name']}.")

            with db_client.get_session() as session:
                last_block = event_loader.get_last_processed_block(
                    session, config["table_name"]
                )

            result = {
                "status": "no_new_data",
                "events_fetched": 0,
                "events_inserted": 0,
                "events_updated": 0,
                "events_skipped": 0,
                "events_errors": 0,
                "entities_upserted": {},
                "last_block_processed": last_block,
            }

            context.add_output_metadata(
                {
                    "events_fetched": dg.MetadataValue.int(result["events_fetched"]),
                    "events_inserted": dg.MetadataValue.int(result["events_inserted"]),
                    "last_block": dg.MetadataValue.int(
                        int(result.get("last_block_processed") or 0)
                    ),
                    "entities": dg.MetadataValue.json(result["entities_upserted"]),
                }
            )

            return result

        df_transformed = transform_output
        entity_stats = upsert_output

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
            "events_fetched": len(df_transformed),
            "events_inserted": load_stats["inserted"],
            "events_updated": load_stats["updated"],
            "events_skipped": load_stats["skipped"],
            "events_errors": load_stats["errors"],
            "entities_upserted": entity_stats,
            "last_block_processed": df_transformed["block_number"].max(),
        }

        context.log.info(f"Asset completed successfully: {result}")

        # Log to Dagster metadata for visibility in UI
        context.add_output_metadata(
            {
                "events_fetched": dg.MetadataValue.int(result["events_fetched"]),
                "events_inserted": dg.MetadataValue.int(result["events_inserted"]),
                "last_block": dg.MetadataValue.int(
                    int(result.get("last_block_processed") or 0)
                ),
                "entities": dg.MetadataValue.json(result["entities_upserted"]),
            }
        )

        return result

    return [_extract_event, _transform_event, _upsert_entities, _load_event]


# Generate all assets programmatically
def generate_all_operator_event_assets():
    """
    Generate all operator event assets from registry.
    Use this if you prefer programmatic generation over explicit definitions.
    """
    assets = []
    for event_name, config in OPERATOR_EVENT_CONFIGS.items():
        event_assets = create_event_extraction_and_load_assets(config=config, first=5)
        assets.extend(event_assets)
    return assets


operator_event_assets = generate_all_operator_event_assets()
