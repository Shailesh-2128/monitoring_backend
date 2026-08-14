import logging
import datetime
import decimal
import uuid
import psycopg2
from django.utils import timezone

logger = logging.getLogger("DatabaseBackupService")


def _format_sql_value(val):
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif isinstance(val, (int, float, decimal.Decimal)):
        return str(val)
    elif isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return f"'{val.isoformat()}'"
    elif isinstance(val, (dict, list)):
        import json
        escaped = json.dumps(val).replace("'", "''")
        return f"'{escaped}'"
    elif isinstance(val, uuid.UUID):
        return f"'{str(val)}'"
    elif isinstance(val, bytes):
        return f"E'\\\\x{val.hex()}'"
    else:
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"


def export_database_sql(database) -> str:
    """
    Generates a full standalone SQL dump file for the given Database model instance.
    Includes DROP TABLE, CREATE TABLE, PRIMARY KEYS, INDEXES, and INSERT data rows.
    """
    db_type = database.db_type
    db_name = database.database_name or database.name
    now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    sql_lines = [
        f"-- ========================================================",
        f"-- SQL Database Backup Dump",
        f"-- Project: {database.project}",
        f"-- Database Name: {database.name} ({db_name})",
        f"-- Engine: {db_type}",
        f"-- Generated At: {now_str}",
        f"-- Host: {database.host}:{database.port}",
        f"-- ========================================================\n",
        "SET statement_timeout = 0;",
        "SET client_encoding = 'UTF8';",
        "SET standard_conforming_strings = on;",
        "SET check_function_bodies = false;",
        "SET xmloption = content;",
        "SET client_min_messages = warning;\n"
    ]

    # Handle MySQL vs PostgreSQL vs SQLite/Other
    if 'mysql' in db_type.lower():
        return _export_mysql_sql(database, sql_lines)
    else:
        return _export_postgresql_sql(database, sql_lines)


def _export_postgresql_sql(database, sql_lines) -> str:
    conn = None
    try:
        if database.connection_uri:
            conn = psycopg2.connect(database.connection_uri, connect_timeout=10)
        else:
            conn = psycopg2.connect(
                host=database.host,
                port=database.port,
                database=database.database_name or 'postgres',
                user=database.username or 'postgres',
                password=database.password or '',
                connect_timeout=10
            )

        cursor = conn.cursor()

        # 1. Fetch all user tables in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            sql_lines.append("-- No tables found in public schema.\n")
            cursor.close()
            conn.close()
            return "\n".join(sql_lines)

        sql_lines.append(f"-- Total Tables Found: {len(tables)}\n")

        # 2. Iterate through each table to export schema and data
        for table in tables:
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"-- Table Structure for `{table}`")
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"DROP TABLE IF EXISTS \"{table}\" CASCADE;")

            # Fetch columns detail
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
            columns_info = cursor.fetchall()

            # Fetch Primary Key
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position;
            """, (table,))
            pk_cols = [r[0] for r in cursor.fetchall()]

            col_defs = []
            col_names = []
            for col_name, data_type, char_len, is_null, col_def in columns_info:
                col_names.append(col_name)
                dtype = data_type.upper()
                if char_len and 'VARCHAR' in dtype:
                    dtype = f"VARCHAR({char_len})"
                
                null_str = "NULL" if is_null == 'YES' else "NOT NULL"
                def_str = f" DEFAULT {col_def}" if col_def else ""
                col_defs.append(f"  \"{col_name}\" {dtype} {null_str}{def_str}")

            if pk_cols:
                pk_str = ", ".join([f"\"{c}\"" for c in pk_cols])
                col_defs.append(f"  PRIMARY KEY ({pk_str})")

            create_stmt = f"CREATE TABLE \"{table}\" (\n" + ",\n".join(col_defs) + "\n);\n"
            sql_lines.append(create_stmt)

            # Fetch Data
            col_clause = ", ".join([f"\"{c}\"" for c in col_names])
            cursor.execute(f"SELECT {col_clause} FROM \"{table}\";")
            rows = cursor.fetchall()

            if rows:
                sql_lines.append(f"-- Data Records for `{table}` ({len(rows)} rows)")
                for r in rows:
                    vals = ", ".join([_format_sql_value(v) for v in r])
                    sql_lines.append(f"INSERT INTO \"{table}\" ({col_clause}) VALUES ({vals});")
                sql_lines.append("")
            else:
                sql_lines.append(f"-- No data rows for `{table}`\n")

        cursor.close()
        conn.close()
        return "\n".join(sql_lines)

    except Exception as e:
        logger.error(f"PostgreSQL SQL Backup Export Error: {e}")
        if conn:
            conn.close()
        raise e


def _export_mysql_sql(database, sql_lines) -> str:
    import pymysql
    conn = None
    try:
        conn = pymysql.connect(
            host=database.host,
            port=database.port,
            database=database.database_name or '',
            user=database.username or 'root',
            password=database.password or '',
            connect_timeout=10
        )
        cursor = conn.cursor()

        cursor.execute("SHOW TABLES;")
        tables = [r[0] for r in cursor.fetchall()]

        if not tables:
            sql_lines.append("-- No tables found in MySQL database.\n")
            cursor.close()
            conn.close()
            return "\n".join(sql_lines)

        for table in tables:
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"-- Table Structure for `{table}`")
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"DROP TABLE IF EXISTS `{table}`;")

            cursor.execute(f"SHOW CREATE TABLE `{table}`;")
            create_stmt = cursor.fetchone()[1]
            sql_lines.append(f"{create_stmt};\n")

            cursor.execute(f"SELECT * FROM `{table}`;")
            rows = cursor.fetchall()
            if rows:
                # Column names
                cursor.execute(f"DESCRIBE `{table}`;")
                cols = [r[0] for r in cursor.fetchall()]
                col_clause = ", ".join([f"`{c}`" for c in cols])

                sql_lines.append(f"-- Data Records for `{table}` ({len(rows)} rows)")
                for r in rows:
                    vals = ", ".join([_format_sql_value(v) for v in r])
                    sql_lines.append(f"INSERT INTO `{table}` ({col_clause}) VALUES ({vals});")
                sql_lines.append("")

        cursor.close()
        conn.close()
        return "\n".join(sql_lines)

    except Exception as e:
        logger.error(f"MySQL SQL Backup Export Error: {e}")
        if conn:
            conn.close()
        raise e


def import_database_sql(database, sql_content: str) -> dict:
    """
    Executes an uploaded SQL backup script against the target database.
    Returns dict with stats (executed_statements, total_statements, status).
    """
    db_type = database.db_type
    
    # Split queries by semicolon outside string literals
    raw_statements = _split_sql_statements(sql_content)
    statements = [stmt for stmt in raw_statements if stmt.strip() and not stmt.strip().startswith('--')]

    if not statements:
        return {"status": "success", "executed_statements": 0, "total_statements": 0, "message": "No executable SQL statements found in file."}

    if 'mysql' in db_type.lower():
        return _import_mysql_sql(database, statements)
    else:
        return _import_postgresql_sql(database, statements)


def _split_sql_statements(sql_content: str) -> list[str]:
    """
    Splits multi-line SQL content into individual query statements.
    """
    statements = []
    current = []
    in_string = False
    quote_char = None
    
    lines = sql_content.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('--') or stripped.startswith('/*'):
            continue
            
        for char in line:
            if char in ("'", '"'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif quote_char == char:
                    in_string = False
                    quote_char = None
            
            if char == ';' and not in_string:
                stmt_str = "".join(current).strip()
                if stmt_str:
                    statements.append(stmt_str)
                current = []
            else:
                current.append(char)
        current.append('\n')

    remaining = "".join(current).strip()
    if remaining:
        statements.append(remaining)

    return statements


def _import_postgresql_sql(database, statements: list[str]) -> dict:
    conn = None
    executed_count = 0
    errors = []

    try:
        # Determine connection parameters with SSL fallback support (same as checker.py)
        if database.connection_uri:
            try:
                conn = psycopg2.connect(database.connection_uri, connect_timeout=10)
            except Exception as uri_err:
                uri = database.connection_uri
                if 'sslmode' not in uri.lower():
                    separator = '&' if '?' in uri else '?'
                    uri_with_ssl = f"{uri}{separator}sslmode=require"
                    try:
                        conn = psycopg2.connect(uri_with_ssl, connect_timeout=10)
                    except Exception:
                        raise uri_err
                else:
                    raise uri_err
        else:
            conn_params = {
                'host': database.host,
                'port': database.port,
                'database': database.database_name or 'postgres',
                'user': database.username or 'postgres',
                'password': database.password or '',
                'connect_timeout': 10
            }
            try:
                conn = psycopg2.connect(**conn_params, sslmode='prefer')
            except Exception:
                try:
                    conn = psycopg2.connect(**conn_params, sslmode='require')
                except Exception:
                    conn = psycopg2.connect(**conn_params, sslmode='allow')

        # Enable autocommit so single statement failures (e.g. unsupported SET commands) don't abort entire import
        conn.autocommit = True
        cursor = conn.cursor()

        # Execute statements in fast multi-statement chunks (batch of 25 statements per packet)
        chunk_size = 25
        for i in range(0, len(statements), chunk_size):
            chunk = statements[i:i + chunk_size]
            batch_sql = ";\n".join(chunk) + ";"
            try:
                cursor.execute(batch_sql)
                executed_count += len(chunk)
            except Exception as batch_err:
                # Fallback to single-statement execution if batch fails
                logger.warning(f"Batch execution failed ({batch_err}), falling back to single statement execution for chunk.")
                for stmt in chunk:
                    try:
                        cursor.execute(stmt)
                        executed_count += 1
                    except Exception as se:
                        err_msg = f"Failed at statement ({stmt[:60]}...): {str(se)}"
                        logger.warning(err_msg)
                        errors.append(err_msg)

        cursor.close()
        conn.close()

        if errors and executed_count == 0:
            raise Exception("; ".join(errors[:3]))

        return {
            "status": "success" if not errors else "partial_success",
            "executed_statements": executed_count,
            "total_statements": len(statements),
            "errors": errors[:5]
        }

    except Exception as e:
        logger.error(f"PostgreSQL SQL Backup Import Error: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise e


def _import_mysql_sql(database, statements: list[str]) -> dict:
    import pymysql
    conn = None
    executed_count = 0
    errors = []

    try:
        conn = pymysql.connect(
            host=database.host,
            port=database.port,
            database=database.database_name or '',
            user=database.username or 'root',
            password=database.password or '',
            connect_timeout=10,
            autocommit=True
        )
        cursor = conn.cursor()

        for stmt in statements:
            try:
                cursor.execute(stmt)
                executed_count += 1
            except Exception as se:
                errors.append(str(se))

        cursor.close()
        conn.close()

        return {
            "status": "success" if not errors else "partial_success",
            "executed_statements": executed_count,
            "total_statements": len(statements),
            "errors": errors[:5]
        }

    except Exception as e:
        logger.error(f"MySQL SQL Backup Import Error: {e}")
        if conn:
            conn.close()
        raise e
