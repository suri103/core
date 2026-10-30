"""Compare ORM metadata against the alembic-migrated schema.

Run: python scripts/check_schema_drift.py

Exits non-zero when the model and the migrations disagree.

**PostgreSQL only.** SQLite cannot support this check: it stores
``postgresql.UUID`` with NUMERIC affinity and has no representation for
TypeDecorators such as ``EncryptedString``, so a SQLite comparison reports dozens
of false positives. When the configured database is not PostgreSQL the check
skips with an explanation rather than reporting noise. CI runs PostgreSQL, so
this is enforced there.

Two checks:

1. A model table or column the migrations never created.
2. A model column whose TYPE disagrees with the migration.

(2) is why this file changed. The previous version only checked (1), so it would
have sailed past ``practices.tax_rate`` being declared JSON in the model while
the baseline migration created it NUMERIC - a mismatch SQLite stores happily and
PostgreSQL rejects at insert time with

  DatatypeMismatchError: column "tax_rate" is of type numeric but expression is
  of type json

Types are compared by family: length, precision and scale legitimately differ
between the model and a migration and are not drift.

3. A model enum column whose enum labels are not all present on the migrated
   Postgres type. SQLAlchemy persists a Python enum's member NAME, so a type
   created from the enum's values - or from a narrower duplicate declaration,
   since SQLAlchemy emits one CREATE TYPE per name and memoizes it - rejects the
   first INSERT carrying the missing label with

     invalid input value for enum <type>: "<LABEL>"

   SQLite cannot catch this class at all: it renders enum columns as plain
   VARCHAR with no CHECK constraint (verified), so the whole local suite stays
   green while PostgreSQL fails. Three instances of this shipped; see
   ``tests/test_enum_migration_parity.py``, which also guards the migration
   source, and revision f4b7c1d9e2a3, which repairs the already-migrated types.

Not compared, deliberately: index lists, nullability, server defaults and enum
*ordering*. Only the enum label SET is compared, in the direction that breaks
INSERTs (model needs a label the database type lacks); extra database labels are
tolerated because Postgres cannot drop enum values and several tables share one
type.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SECRET_KEY", "drift-check-key-not-for-production-usage")
os.environ.setdefault("ENCRYPTION_KEY", "dHJ1c3RlZC10ZXN0LWtleS1mb3ItZHJpZnQtY2hlY2s=")
os.environ.setdefault("ENVIRONMENT", "test")

# Model type name -> acceptable reflected type names. Types absent from this map
# are reported as not-compared rather than silently skipped, so a new column type
# cannot quietly opt out of the check.
_COMPARABLE = {
    "JSON": {"JSON", "JSONB"},
    "Numeric": {"NUMERIC", "DECIMAL"},
    "Float": {"FLOAT", "REAL", "DOUBLE PRECISION", "NUMERIC"},
    "BigInteger": {"BIGINT", "BIGINTEGER"},
    "Integer": {"INTEGER", "BIGINT", "SMALLINT"},
    "SmallInteger": {"SMALLINT", "INTEGER"},
    "Boolean": {"BOOLEAN"},
    "DateTime": {"TIMESTAMP", "DATETIME", "TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP WITH TIME ZONE"},
    "Date": {"DATE"},
    "Time": {"TIME"},
    "Text": {"TEXT"},
    "String": {"VARCHAR", "CHARACTER VARYING", "CHAR", "CHARACTER", "TEXT"},
    "LargeBinary": {"BYTEA"},
    "UUID": {"UUID"},
}


def model_type_names(column) -> list[str]:
    """Candidate model type names, unwrapping TypeDecorators.

    ``EncryptedString`` wraps VARCHAR, ``EncryptedJSON`` wraps JSON. Comparing
    the decorator's own name would flag every encrypted column, so the
    underlying type is used.
    """
    names = []
    for klass in type(column.type).__mro__:
        if klass.__name__ in ("TypeDecorator", "TypeEngine", "object"):
            break
        names.append(klass.__name__)
    impl = getattr(column.type, "impl", None)
    if impl is not None:
        for klass in type(impl).__mro__:
            if klass.__name__ in ("TypeEngine", "object"):
                break
            names.append(klass.__name__)
    return names


def acceptable(column) -> set[str] | None:
    for name in model_type_names(column):
        if name in _COMPARABLE:
            return _COMPARABLE[name]
    return None


def model_enum_labels(column) -> tuple[str, set[str]] | None:
    """(type name, required labels) when the model column is an Enum."""
    from sqlalchemy import Enum as SAEnum

    for candidate in (column.type, getattr(column.type, "impl", None)):
        if isinstance(candidate, SAEnum) and candidate.enums:
            return candidate.name, set(candidate.enums)
    return None


def reflected_enum_labels(inspector, table_name: str) -> dict[str, set[str]]:
    """Labels per column for columns PostgreSQL stores as an enum.

    Empty when the dialect does not reflect labels, so a reflection surprise
    skips the comparison instead of reporting drift that is not real.
    """
    labelled: dict[str, set[str]] = {}
    for reflected in inspector.get_columns(table_name):
        enums = getattr(reflected["type"], "enums", None)
        if enums:
            labelled[reflected["name"]] = set(enums)
    return labelled


def main() -> int:
    from sqlalchemy import create_engine, inspect

    from app.core.config_simple import settings
    import app.models  # noqa: F401
    from app.core.base import Base

    url = settings.DATABASE_URL or ""
    sync_url = url.replace("+asyncpg", "").replace("+aiosqlite", "")
    if not sync_url.startswith("postgres"):
        print(
            "SKIP: schema drift check requires PostgreSQL.\n"
            "  Configured database is not PostgreSQL, and SQLite cannot compare\n"
            "  types meaningfully (UUID lands as NUMERIC and TypeDecorators are\n"
            "  not representable). This check runs in CI against PostgreSQL."
        )
        return 0

    engine = create_engine(sync_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    missing: list[str] = []
    drifted: list[str] = []
    enum_drift: list[str] = []
    not_compared: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in table_names:
            missing.append(f"{table.name} (<entire table missing>)")
            continue

        columns = inspector.get_columns(table.name)
        actual = {col["name"]: str(col["type"]).upper() for col in columns}
        db_enum_labels = reflected_enum_labels(inspector, table.name)
        for column in table.columns:
            if column.name not in actual:
                missing.append(f"{table.name}.{column.name}")
                continue

            enum_spec = model_enum_labels(column)
            if enum_spec is not None and column.name in db_enum_labels:
                type_name, required = enum_spec
                absent = sorted(required - db_enum_labels[column.name])
                if absent:
                    enum_drift.append(
                        f"{table.name}.{column.name}: the model writes {absent}, "
                        f"which the migrated {type_name} type does not accept"
                    )
                continue

            accepted = acceptable(column)
            if accepted is None:
                not_compared.append(f"{table.name}.{column.name} ({type(column.type).__name__})")
                continue
            declared = actual[column.name]
            if not any(name in declared for name in accepted):
                drifted.append(
                    f"{table.name}.{column.name}: model says "
                    f"{type(column.type).__name__}, migration created {declared}"
                )

    engine.dispose()

    if missing or drifted or enum_drift:
        if missing:
            print("SCHEMA DRIFT: model tables/columns absent from the migrated database:")
            for item in missing:
                print(f"  {item}")
        if drifted:
            print("SCHEMA DRIFT: model column types disagree with the migrations:")
            for item in drifted:
                print(f"  {item}")
        if enum_drift:
            print(
                "SCHEMA DRIFT: enum labels the model writes are absent from the "
                "migrated type (the first INSERT carrying one fails on PostgreSQL):"
            )
            for item in enum_drift:
                print(f"  {item}")
        print(
            "\nSQLite tolerates these mismatches; PostgreSQL enforces them and "
            "rejects the INSERT at runtime. Fix the model or add a migration."
        )
        return 1

    print(f"No schema drift: {len(not_compared)} column(s) had no comparable type mapping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
