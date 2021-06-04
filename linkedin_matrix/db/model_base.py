class Model:
    _table_name: str
    _field_list: str

    @classmethod
    def select_constructor(cls, where_clause: str = None) -> str:
        query = f'SELECT {cls._field_list} FROM "{cls._table_name}"'
        if where_clause:
            query += f" WHERE {where_clause}"
        return query

    @classmethod
    def insert_constructor(cls) -> str:
        values_str = ",".join(f"${i+1}" for i in range(len((cls._field_list))))
        return f"""
            INSERT INTO "{cls._table_name}" ({cls._field_list})
            VALUES ({values_str})
        """
