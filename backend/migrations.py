from sqlalchemy import inspect, text


def ensure_attendance_schema(engine) -> None:
    """Lightweight migration for SQLite to support hourly attendance slots."""
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "attendance" not in tables:
            return

        columns = {col["name"] for col in inspector.get_columns("attendance")}
        if "attendance_hour" in columns:
            return

        conn.execute(
            text(
                """
                CREATE TABLE attendance_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    attendance_date DATE NOT NULL,
                    attendance_hour INTEGER NOT NULL DEFAULT 0,
                    attendance_time TIME NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    confidence FLOAT NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                    CONSTRAINT uq_user_attendance_per_slot UNIQUE (user_id, attendance_date, attendance_hour)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO attendance_new (
                    id, user_id, attendance_date, attendance_hour, attendance_time, status, confidence, created_at
                )
                SELECT
                    id,
                    user_id,
                    attendance_date,
                    CAST(strftime('%H', attendance_time) AS INTEGER),
                    attendance_time,
                    status,
                    confidence,
                    created_at
                FROM attendance
                """
            )
        )
        conn.execute(text("DROP TABLE attendance"))
        conn.execute(text("ALTER TABLE attendance_new RENAME TO attendance"))
