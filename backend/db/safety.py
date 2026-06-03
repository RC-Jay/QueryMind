import re
import sqlglot
from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


class SQLSafetyValidator:
    BLOCKED_KEYWORDS = {
        "drop", "delete", "insert", "update", "alter", "create",
        "truncate", "grant", "revoke", "replace", "merge", "call",
        "exec", "execute",
    }
    BLOCKED_TABLE_PATTERN = re.compile(r".*_event$", re.IGNORECASE)

    def validate(self, sql: str) -> ValidationResult:
        # 1. Keyword blocklist on raw SQL
        lowered = sql.lower()
        for kw in self.BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", lowered):
                return ValidationResult(ok=False, reason=f"Blocked keyword: {kw.upper()}")

        # 2. AST-level check — top-level statement must be SELECT
        try:
            statements = sqlglot.parse(sql, dialect="postgres")
        except Exception as exc:
            return ValidationResult(ok=False, reason=f"SQL parse error: {exc}")

        if not statements:
            return ValidationResult(ok=False, reason="Empty query")

        for stmt in statements:
            if not isinstance(stmt, sqlglot.expressions.Select):
                return ValidationResult(ok=False, reason="Only SELECT statements are allowed")

        # 3. Block _event tables
        for stmt in statements:
            for table in stmt.find_all(sqlglot.expressions.Table):
                name = table.name or ""
                if self.BLOCKED_TABLE_PATTERN.match(name):
                    return ValidationResult(ok=False, reason=f"Querying audit tables is not allowed: {name}")

        return ValidationResult(ok=True)


_validator = SQLSafetyValidator()


def validate_sql(sql: str) -> ValidationResult:
    return _validator.validate(sql)
