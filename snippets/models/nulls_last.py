from django.db import connections, models
from django.db.models.sql.compiler import SQLCompiler


class NullsLastSQLCompiler(SQLCompiler):
    def get_order_by(self):
        result = super(NullsLastSQLCompiler, self).get_order_by()
        if result and self.connection.vendor == 'postgresql':
            return [(expr, (sql + ' NULLS LAST', params, is_ref))
                    for (expr, (sql, params, is_ref)) in result]
        return result


class NullsLastQuery(models.sql.query.Query):
    """Use a custom compiler to inject 'NULLS LAST' (for PostgreSQL)."""
    def __init__(self, *args, **kwargs):
        super(NullsLastQuery, self).__init__(*args, **kwargs)

    def get_compiler(self, using=None, connection=None):
        if using is None and connection is None:
            raise ValueError('Need either using or connection')
        if using:
            connection = connections[using]
        return NullsLastSQLCompiler(self, connection, using)


class NullsLastQuerySet(models.QuerySet):
    def __init__(self, model=None, query=None, using=None, hints=None):
        super(NullsLastQuerySet, self).__init__(model=model, query=query, using=using, hints=hints)
        self.query = query or NullsLastQuery(self.model)
