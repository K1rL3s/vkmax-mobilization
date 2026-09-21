from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.sql.elements import SQLColumnExpression

from zheka.core.ids import OrgId
from zheka.infra.database.tables.houses import houses_table


def scoped_to_org[SelectT: Select[Any]](
    stmt: SelectT,
    house_column: SQLColumnExpression[int],
    org_id: OrgId,
) -> SelectT:
    org_houses = select(houses_table.c.id).where(houses_table.c.org_id == org_id)
    return stmt.where(house_column.in_(org_houses))
