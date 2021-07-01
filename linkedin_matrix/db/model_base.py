from typing import ClassVar, List, TYPE_CHECKING

from mautrix.util.async_db import Database

fake_db = Database("") if TYPE_CHECKING else None


class Model:
    db: ClassVar[Database] = fake_db

    _table_name: str
    _field_list: List[str]

    @classmethod
    def select_constructor(cls, where_clause: str = None) -> str:
        query = f'SELECT {",".join(cls._field_list)} FROM "{cls._table_name}"'
        if where_clause:
            query += f" WHERE {where_clause}"
        return query

    @classmethod
    def insert_constructor(cls) -> str:
        values_str = ",".join(f"${i+1}" for i in range(len(cls._field_list)))
        return f"""
            INSERT INTO "{cls._table_name}" ({",".join(cls._field_list)})
            VALUES ({values_str})
        """
