from sqlalchemy import PrimaryKeyConstraint, Table, UniqueConstraint

from zheka.infra.database.tables import metadata


def _leading_columns(table: Table) -> set[str]:
    keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, PrimaryKeyConstraint | UniqueConstraint)
    ]
    return {
        next(iter(each.columns)).name
        for each in [*table.indexes, *keys]
        if len(each.columns)
    }


def test_every_foreign_key_leads_an_index() -> None:
    missing = [
        f"{table.name}.{fk.parent.name}"
        for table in metadata.sorted_tables
        for fk in table.foreign_keys
        if fk.parent.name not in _leading_columns(table)
    ]

    assert missing == []
