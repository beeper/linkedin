from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from mautrix.util.async_db import Database

fake_db = Database("") if TYPE_CHECKING else None


class Model:
    # Ignore type errors here since the variable will always be set in db/__init__.py.
    db: ClassVar[Database] = fake_db  # type: ignore

    _table_name: str
    _field_list: list[str]

    @classmethod
    def field_list_str(cls) -> str:
        return ",".join(map(lambda f: f'"{f}"', cls._field_list))

    @classmethod
    def select_constructor(cls, where_clause: str | None = None) -> str:
        query = f'SELECT {cls.field_list_str()} FROM "{cls._table_name}"'
        if where_clause:
            query += f" WHERE {where_clause}"
        return query

    @classmethod
    def insert_constructor(cls) -> str:
        values_str = ",".join(f"${i+1}" for i in range(len(cls._field_list)))
        return f"""
            INSERT INTO "{cls._table_name}" ({cls.field_list_str()})
            VALUES ({values_str})
        """
