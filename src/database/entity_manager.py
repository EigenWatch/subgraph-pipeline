"""
Entity manager for upserting lookup entities (Operator, Staker, AVS, etc.)
Handles idempotent inserts with conflict resolution.
"""

from typing import List, Dict
from datetime import datetime, timezone

import dagster as dg
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models.entities import Operator


class EntityManager(dg.ConfigurableResource):
    """
    Manages upserts for entity lookup tables.
    All methods are idempotent and safe to call multiple times.
    """

    def upsert_operators(
        self,
        session: Session,
        operator_ids: List[str],
        context: dg.OpExecutionContext = None,
    ) -> Dict[str, int]:
        """
        Upsert operators by ID (address).

        Args:
            session: SQLAlchemy session
            operator_ids: List of operator addresses (hex strings)
            context: Dagster context for logging

        Returns:
            {"inserted": X, "updated": Y, "skipped": Z}
        """
        if not operator_ids:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        # Remove duplicates
        unique_ids = list(set(operator_ids))

        inserted = 0
        updated = 0
        skipped = 0

        for operator_id in unique_ids:
            try:
                # Use PostgreSQL INSERT ... ON CONFLICT
                stmt = insert(Operator).values(
                    id=operator_id,
                    address=operator_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                # On conflict, update the updated_at timestamp
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "updated_at": datetime.now(timezone.utc),
                    },
                ).returning(Operator.id, Operator.created_at, Operator.updated_at)

                result = session.execute(stmt)

                # Check if row was inserted or updated
                if result.rowcount > 0:
                    row = result.fetchone()
                    if row.created_at == row.updated_at:
                        inserted += 1
                    else:
                        updated += 1
                else:
                    skipped += 1

            except Exception as e:
                if context:
                    context.log.warning(f"Failed to upsert operator {operator_id}: {e}")
                skipped += 1
                continue

        if context:
            context.log.info(
                f"Operator upsert: {inserted} inserted, {updated} updated, "
                f"{skipped} skipped out of {len(unique_ids)} total"
            )

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
        }

    def upsert_stakers(
        self,
        session: Session,
        staker_ids: List[str],
        context: dg.OpExecutionContext = None,
    ) -> Dict[str, int]:
        """
        Upsert stakers by ID (address).
        Implementation follows same pattern as upsert_operators.
        TODO: Implement when we add staker events.
        """
        # Placeholder for future implementation
        return {"inserted": 0, "updated": 0, "skipped": 0}

    def upsert_avs(
        self,
        session: Session,
        avs_ids: List[str],
        context: dg.OpExecutionContext = None,
    ) -> Dict[str, int]:
        """
        Upsert AVS by ID (address).
        TODO: Implement when we add AVS events.
        """
        return {"inserted": 0, "updated": 0, "skipped": 0}

    def upsert_strategies(
        self,
        session: Session,
        strategy_ids: List[str],
        context: dg.OpExecutionContext = None,
    ) -> Dict[str, int]:
        """
        Upsert strategies by ID (address).
        TODO: Implement when we add strategy events.
        """
        return {"inserted": 0, "updated": 0, "skipped": 0}

    def upsert_operator_sets(
        self,
        session: Session,
        operator_set_data: List[Dict[str, any]],
        context: dg.OpExecutionContext = None,
    ) -> Dict[str, int]:
        """
        Upsert operator sets (composite key: avs_id + operator_set_id).

        Args:
            operator_set_data: List of dicts with keys: id, avs_id, operator_set_id

        TODO: Implement when we add operator set events.
        """
        return {"inserted": 0, "updated": 0, "skipped": 0}
