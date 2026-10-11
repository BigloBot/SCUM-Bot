from datetime import datetime, timezone

from app.core import settings
from app.core.database import get_db


def _parse_timestamp(value: str) -> datetime:
    """SQLite CURRENT_TIMESTAMP is UTC text like '2026-10-10 21:30:00'."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


class BankRepository:
    @staticmethod
    def get_resource_types():
        """The materials tracked in every stockpile (active only), in display order."""
        with get_db() as conn:
            return conn.execute(
                "SELECT label FROM bank_resource_types WHERE active = 1 ORDER BY sort_order, id"
            ).fetchall()

    @staticmethod
    def check_duplicate(name: str) -> bool:
        """True if an ACTIVE stockpile in the current war already has this name. The passcode is not unique."""
        war_number = settings.get_active_war()
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM bank_stockpiles WHERE name = ? COLLATE NOCASE AND war_number = ? AND status = 'ACTIVE'",
                (name, war_number)
            ).fetchone()
        return row is not None

    @staticmethod
    def add_stockpile(name: str, code: str, location: str, user_id: str) -> int:
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bank_stockpiles (war_number, name, code, location, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (war_number, name, code, location, user_id)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_stockpile(stockpile_id: int):
        with get_db() as conn:
            return conn.execute("SELECT * FROM bank_stockpiles WHERE id = ?", (stockpile_id,)).fetchone()

    @staticmethod
    def get_stockpiles(war_number: int = None, status: str = "ACTIVE"):
        """Stockpiles of a war (the active war by default) in creation order."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            return conn.execute(
                "SELECT * FROM bank_stockpiles WHERE war_number = ? AND status = ? ORDER BY id",
                (war_number, status)
            ).fetchall()

    @staticmethod
    def delete_stockpile(stockpile_id: int):
        """Soft delete only: the stockpile and its transaction history are kept for reporting."""
        with get_db() as conn:
            conn.execute(
                "UPDATE bank_stockpiles SET status = 'DELETED' WHERE id = ? AND status = 'ACTIVE'",
                (stockpile_id,)
            )
            conn.commit()

    @staticmethod
    def set_message_id(stockpile_id: int, message_id: str | None):
        with get_db() as conn:
            conn.execute("UPDATE bank_stockpiles SET message_id = ? WHERE id = ?", (message_id, stockpile_id))
            conn.commit()

    @staticmethod
    def get_stockpiles_with_messages():
        """Every stockpile (any war or status) that still has a board message posted."""
        with get_db() as conn:
            return conn.execute("SELECT id, message_id FROM bank_stockpiles WHERE message_id IS NOT NULL").fetchall()

    @staticmethod
    def clear_all_message_ids():
        with get_db() as conn:
            conn.execute("UPDATE bank_stockpiles SET message_id = NULL")
            conn.commit()

    @staticmethod
    def _balances(conn, stockpile_id: int) -> dict[str, int]:
        labels = [r["label"] for r in conn.execute(
            "SELECT label FROM bank_resource_types WHERE active = 1 ORDER BY sort_order, id"
        )]
        totals = {label: 0 for label in labels}
        for row in conn.execute(
            "SELECT resource, SUM(amount) AS total FROM bank_transactions WHERE stockpile_id = ? GROUP BY resource",
            (stockpile_id,)
        ):
            if row["resource"] in totals:
                totals[row["resource"]] = row["total"]
        return totals

    @staticmethod
    def get_summary(stockpile_id: int) -> tuple[dict[str, int], datetime]:
        """Current amount of every tracked material, and when the stockpile last changed."""
        with get_db() as conn:
            balances = BankRepository._balances(conn, stockpile_id)
            row = conn.execute(
                """
                SELECT COALESCE(
                    (SELECT MAX(created_at) FROM bank_transactions WHERE stockpile_id = ?),
                    (SELECT created_at FROM bank_stockpiles WHERE id = ?)
                ) AS last_updated
                """,
                (stockpile_id, stockpile_id)
            ).fetchone()
        return balances, _parse_timestamp(row["last_updated"])

    @staticmethod
    def set_balances(stockpile_id: int, amounts: dict[str, int], user_id: str) -> list[tuple[str, int, int]]:
        """
        Sets the amount of each given material. Only the difference is recorded as a transaction.
        Returns (material, old amount, new amount) for everything that changed.
        """
        changes = []
        with get_db() as conn:
            current = BankRepository._balances(conn, stockpile_id)
            for label, new_amount in amounts.items():
                old_amount = current.get(label, 0)
                if new_amount == old_amount:
                    continue
                conn.execute(
                    "INSERT INTO bank_transactions (stockpile_id, resource, amount, user_id) VALUES (?, ?, ?, ?)",
                    (stockpile_id, label, new_amount - old_amount, user_id)
                )
                changes.append((label, old_amount, new_amount))
            conn.commit()
        return changes
