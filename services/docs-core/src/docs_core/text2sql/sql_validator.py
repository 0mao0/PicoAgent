"""Text-to-SQL 的 SQL 校验。"""
import re


ALLOWED_TABLES = {
    "canonical_documents",
    "canonical_chunks",
    "canonical_tables",
    "canonical_blocks",
    "canonical_outlines",
}


# 校验生成 SQL 是否满足只读白名单约束。
def validate_sql(sql: str) -> tuple[bool, str]:
    normalized_sql = " ".join((sql or "").strip().split())
    if not normalized_sql:
        return False, "empty_sql"
    if ";" in normalized_sql:
        return False, "semicolon_not_allowed"
    if not normalized_sql.upper().startswith("SELECT COUNT(*) AS TOTAL_COUNT FROM "):
        return False, "only_count_select_supported"
    if any(keyword in normalized_sql.upper() for keyword in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "ATTACH ")):
        return False, "write_operation_not_allowed"
    table_match = re.search(r"FROM\s+([A-Za-z_][A-Za-z0-9_]*)", normalized_sql, flags=re.IGNORECASE)
    if not table_match:
        return False, "missing_table_name"
    table_name = table_match.group(1)
    if table_name not in ALLOWED_TABLES:
        return False, f"table_not_allowed:{table_name}"
    return True, "ok"
