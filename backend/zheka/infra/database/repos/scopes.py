from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.sql.elements import SQLColumnExpression

from zheka.core.ids import OrgId
from zheka.infra.database.tables.houses import houses_table


def org_house_ids(org_id: OrgId) -> Select[tuple[int]]:
    return select(houses_table.c.id).where(houses_table.c.org_id == org_id)


# SQLColumnExpression is SQLAlchemy's public type for "usable in a WHERE",
# covering both a Table.c column and an ORM InstrumentedAttribute
def scoped_to_org[SelectT: Select[Any]](
    stmt: SelectT,
    house_column: SQLColumnExpression[int],
    org_id: OrgId,
) -> SelectT:
    return stmt.where(house_column.in_(org_house_ids(org_id)))
