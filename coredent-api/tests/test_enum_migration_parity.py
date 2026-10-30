"""Enum-label and migration-chain guards (no database required).

A Postgres enum type is a single shared object per name. When a migration (or a
column declaration) creates the same type name twice with different member sets,
SQLAlchemy emits one ``CREATE TYPE`` and memoizes it: only the first
declaration's labels exist for the whole type, and every INSERT carrying a label
from any other declaration fails at runtime with

  invalid input value for enum <type>: "<LABEL>"

This is invisible to the SQLite test suite, which renders each column as VARCHAR
plus a CHECK generated from that column's own declaration, so the failure only
appears against the real database. It shipped once already: ``messagestatus``
was missing SENDING (breaking every PatientMessage delivery), and
``paymentstatus``/``paymentmethod`` were declared twice with different members.

These tests compare the ORM metadata against the migration source, so they run
everywhere and gate the class in CI without a database.
"""
import re
from collections import defaultdict
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"

# sa.Enum('A', 'B', name='x') | sa.Enum(*_CONST, name="x", create_type=False)
_ENUM_CALL = re.compile(
    r"\bEnum\(\s*([^)]*)\)",
    re.DOTALL,
)
_QUOTED_NAME = re.compile(r"name\s*=\s*['\"]([a-z_][a-z0-9_]*)['\"]")
_SPLAT = re.compile(r"\*\s*([A-Za-z_][A-Za-z0-9_]*)")
_STRING_LITERAL = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")
_CONSTANT = re.compile(
    r"^_?([A-Z][A-Z0-9_]*)\s*=\s*\(([^)]*)\)",
    re.MULTILINE | re.DOTALL,
)
_ADD_VALUE = re.compile(
    r"ALTER\s+TYPE\s+([a-z_][a-z0-9_]*)\s+ADD\s+VALUE\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
    re.IGNORECASE,
)
# Files whose ADD VALUE statements interpolate the label instead of naming it.
_ADD_VALUE_TYPE = re.compile(
    r"ALTER\s+TYPE\s+([a-z_][a-z0-9_]*)\s+ADD\s+VALUE", re.IGNORECASE
)
_TUPLE_LITERAL = re.compile(r"\(([^()]*)\)")
_LIST_LITERAL = re.compile(r"\[([^\[\]]*)\]")
_UPPERCASE_LITERAL = re.compile(r"['\"]([A-Z][A-Z0-9_]*)['\"]")
# Helper calls that take the type name as a literal argument, e.g.
# _add_enum_members(bind, "userrole", _NEW_MEMBERS) — the ALTER statement itself
# interpolates the name, so only the call site is greppable.
_ENUM_HELPER_CALL = re.compile(r"_add_enum_members\s*\(([^)]*)\)", re.DOTALL)
_LOWERCASE_LITERAL = re.compile(r"['\"]([a-z_][a-z0-9_]*)['\"]")
_REVISION = re.compile(
    r"^revision\s*(?::\s*str\s*)?=\s*['\"]([^'\"]+)['\"]", re.MULTILINE
)
_DOWN_REVISION = re.compile(
    r"^down_revision\s*(?::[^=]*)?=\s*(?:['\"]([^'\"]+)['\"]|None)", re.MULTILINE
)

# Model enum types no migration creates as a Postgres enum. These are known,
# deliberate, and harmless today: the ORM writes the plain string value and the
# migrated column is VARCHAR, so inserts behave. Listed explicitly so the guard
# still fails on any NEW undeclared type instead of silently tolerating drift.
_KNOWN_MODEL_ONLY_ENUMS = {
    # baseline bb372b5f2d4a declares this column sa.String(length=50) while
    # models/billing.py declares Enum(InstallmentStatus).
    "installmentstatus",
}


def _migration_texts() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(MIGRATIONS_DIR.glob("*.py"))
    }


def _module_constants(text: str) -> dict[str, set[str]]:
    """Uppercase tuple/list constants, e.g. _PROCESSOR_EVENT_STATUS = ("A", "B")."""
    return {
        match.group(1): set(_STRING_LITERAL.findall(match.group(2)))
        for match in _CONSTANT.finditer(text)
    }


def _declared_enum_members() -> dict[str, list[tuple[str, frozenset[str]]]]:
    """Per enum type name: every declaration site and the labels it declares."""
    declared: dict[str, list[tuple[str, frozenset[str]]]] = defaultdict(list)
    for filename, text in _migration_texts().items():
        constants = _module_constants(text)
        for match in _ENUM_CALL.finditer(text):
            body = match.group(1)
            name_match = _QUOTED_NAME.search(body)
            if not name_match:
                continue
            type_name = name_match.group(1)

            members: set[str] = set()
            for splat in _SPLAT.findall(body):
                members |= constants.get(splat.lstrip("_"), set())
            # Inline literals, excluding the type name itself.
            members |= set(_STRING_LITERAL.findall(body)) - {type_name}
            if not members:
                # e.g. sa.Enum(name="x").drop(...) — not a declaration.
                continue
            declared[type_name].append((filename, frozenset(members)))
    return declared


def _added_enum_members() -> dict[str, set[str]]:
    """Per enum type name: labels added by the migrations after creation.

    Two shapes exist in this tree: literal ``ALTER TYPE x ADD VALUE 'A'``
    statements, and helpers/loops that interpolate the label into the statement
    (the label set then lives in a tuple or module constant in the same file).
    Both are collected; for the interpolated form every uppercase string in a
    tuple/list literal in that file is credited to the file's ADD VALUE types.
    That over-credits at worst (a label that another statement in the same file
    adds), which weakens the check but can never make it wrong in the failing
    direction.
    """
    added: dict[str, set[str]] = defaultdict(set)
    for text in _migration_texts().values():
        for type_name, label in _ADD_VALUE.findall(text):
            added[type_name.lower()].add(label)

        types_in_file = {
            type_name.lower()
            for type_name in _ADD_VALUE_TYPE.findall(text)
            if type_name
        }
        for call_args in _ENUM_HELPER_CALL.findall(text):
            types_in_file |= set(_LOWERCASE_LITERAL.findall(call_args))
        if not types_in_file:
            continue
        literal_groups = _TUPLE_LITERAL.findall(text) + _LIST_LITERAL.findall(text)
        file_labels = set()
        for group in literal_groups:
            file_labels |= set(_UPPERCASE_LITERAL.findall(group))
        for type_name in types_in_file:
            added[type_name] |= file_labels
    return added


def _model_enum_columns():
    """(path, type_name, required labels) for every enum-typed model column."""
    import app.models  # noqa: F401  (populate the metadata)
    from app.core.base import Base
    from sqlalchemy import Enum as SAEnum

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            candidates = [column.type, getattr(column.type, "impl", None)]
            for candidate in candidates:
                if isinstance(candidate, SAEnum) and candidate.enums:
                    yield (
                        f"{table.name}.{column.name}",
                        candidate.name,
                        set(candidate.enums),
                    )
                    break


def test_no_enum_type_is_declared_with_different_members():
    problems = []
    for type_name, declarations in sorted(_declared_enum_members().items()):
        distinct = {members for _, members in declarations}
        if len(distinct) < 2:
            continue
        union = set().union(*distinct)
        details = "; ".join(
            f"{filename} lacks {sorted(union - members)}"
            for filename, members in declarations
            if union - members
        )
        problems.append(f"{type_name}: {details}")
    assert not problems, (
        "An enum type name is one shared Postgres object. Declaring it twice with "
        "different members means only the first declaration's labels exist, so "
        "inserts using the others fail at runtime (see this module's docstring):\n  "
        + "\n  ".join(problems)
    )


def test_every_model_enum_label_exists_on_the_migrated_type():
    declared = _declared_enum_members()
    added = _added_enum_members()

    missing = []
    undeclared_types = []
    for column_path, type_name, required in _model_enum_columns():
        if type_name not in declared:
            if type_name not in _KNOWN_MODEL_ONLY_ENUMS:
                undeclared_types.append(f"{column_path} -> {type_name}")
            continue
        available = (
            set().union(*[members for _, members in declared[type_name]])
            | added.get(type_name, set())
        )
        gap = sorted(required - available)
        if gap:
            missing.append(f"{column_path} ({type_name}) is missing {gap}")

    assert not undeclared_types, (
        "Model enum types no migration ever declares (the type will not exist in "
        "a migrated database):\n  " + "\n  ".join(undeclared_types)
    )
    assert not missing, (
        "These enum labels are written by the ORM but absent from the migrated "
        "type; the first INSERT carrying one fails on PostgreSQL. Add them to a "
        "migration (ALTER TYPE ... ADD VALUE IF NOT EXISTS) — SQLite will not "
        "catch this:\n  " + "\n  ".join(missing)
    )


def test_migration_chain_has_exactly_one_head():
    revisions: dict[str, str | None] = {}
    filenames: dict[str, str] = {}
    for filename, text in _migration_texts().items():
        revision_match = _REVISION.search(text)
        if not revision_match:
            continue
        revision = revision_match.group(1)
        down_match = _DOWN_REVISION.search(text)
        revisions[revision] = down_match.group(1) if down_match else None
        filenames[revision] = filename

    referenced = {parent for parent in revisions.values() if parent}
    unknown_parents = sorted(referenced - set(revisions))
    heads = sorted(set(revisions) - referenced)

    assert not unknown_parents, f"down_revision points at unknown revisions: {unknown_parents}"
    assert len(heads) == 1, (
        f"expected exactly one head revision, found {len(heads)}: "
        f"{[filenames.get(head, head) for head in heads]}"
    )
