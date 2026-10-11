from app.core import settings
from app.core.database import get_db

class AirfieldRepository:
    @staticmethod
    def _active_depot_id(conn, airfield_id: int, war_number: int) -> int | None:
        """Confirms the depot is ACTIVE in the given war; the passcode is not unique, so depots are addressed by id."""
        row = conn.execute(
            "SELECT id FROM airfields WHERE id = ? AND war_number = ? AND status = 'ACTIVE'",
            (airfield_id, war_number)
        ).fetchone()
        return row["id"] if row else None

    @staticmethod
    def add_airfield(name: str, code: str, location: str, thread_id: str = None):
        war_number = settings.get_active_war()
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO airfields (code, name, location, thread_id, war_number, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (code.upper(), name.upper(), location, thread_id, war_number)
            )
            conn.commit()

    @staticmethod
    def check_duplicate(name: str) -> bool:
        """True if an ACTIVE depot in the current war already has this name. The passcode is not unique."""
        war_number = settings.get_active_war()
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM airfields WHERE name = ? AND war_number = ? AND status = 'ACTIVE'",
                (name.upper(), war_number)
            ).fetchone()
        return row is not None

    @staticmethod
    def delete_airfield(airfield_id: int):
        """Soft delete only: the row and all of its plane history are kept for reporting."""
        with get_db() as conn:
            conn.execute("UPDATE airfields SET status = 'DELETED' WHERE id = ? AND status = 'ACTIVE'", (airfield_id,))
            conn.commit()

    @staticmethod
    def get_airfields(war_number: int = None, status: str = 'ACTIVE'):
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, code, name, location, thread_id, war_number, status FROM airfields WHERE war_number = ? AND status = ? ORDER BY name ASC",
                (war_number, status)
            )
            return cursor.fetchall()

    @staticmethod
    def get_all_war_airfields():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, code, name, location, thread_id, war_number, status FROM airfields")
            return cursor.fetchall()

    @staticmethod
    def get_aircraft_types():
        """The predetermined aircraft list (active only), in display order. `label` is what planes store."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, role, label FROM aircraft_types WHERE active = 1 ORDER BY sort_order, id"
            )
            return cursor.fetchall()

    @staticmethod
    def get_depot_by_id(airfield_id: int):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, code, name, location, thread_id, war_number, status FROM airfields WHERE id = ?",
                (airfield_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def add_plane(airfield_id: int, plane_type: str, user_id: str) -> bool:
        war_number = settings.get_active_war()
        with get_db() as conn:
            airfield_id = AirfieldRepository._active_depot_id(conn, airfield_id, war_number)
            if airfield_id is None:
                return False
            conn.execute(
                """
                INSERT INTO plane_instances (war_number, airfield_id, plane_type, added_by, status)
                VALUES (?, ?, ?, ?, 'IN_STOCK')
                """,
                (war_number, airfield_id, plane_type, user_id)
            )
            conn.commit()
            return True

    @staticmethod
    def get_available_planes(airfield_id: int):
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.plane_type, COUNT(*) as count
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE a.war_number = ? AND a.id = ? AND a.status = 'ACTIVE' AND p.status = 'IN_STOCK'
                GROUP BY p.plane_type
                HAVING count > 0
                """,
                (war_number, airfield_id)
            )
            return cursor.fetchall()

    @staticmethod
    def get_stock_summary(airfield_id: int):
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.plane_type, COUNT(*) as count
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE a.war_number = ? AND a.id = ? AND a.status = 'ACTIVE' AND p.status = 'IN_STOCK'
                GROUP BY p.plane_type
                """,
                (war_number, airfield_id)
            )
            return cursor.fetchall()

    @staticmethod
    def get_user_active_flight(user_id: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.id, p.war_number, p.airfield_id, a.code AS airfield_code, p.plane_type, p.usecase
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE p.removed_by = ? AND p.status = 'CHECKED_OUT'
                LIMIT 1
                """,
                (str(user_id),)
            )
            return cursor.fetchone()

    @staticmethod
    def checkout_plane(airfield_id: int, plane_type: str, usecase: str, user_id: str) -> bool:
        if AirfieldRepository.get_user_active_flight(user_id):
            return False

        war_number = settings.get_active_war()
        with get_db() as conn:
            airfield_id = AirfieldRepository._active_depot_id(conn, airfield_id, war_number)
            if airfield_id is None:
                return False

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM plane_instances
                WHERE airfield_id = ? AND plane_type = ? AND status = 'IN_STOCK'
                LIMIT 1
                """,
                (airfield_id, plane_type)
            )
            row = cursor.fetchone()
            if row:
                plane_id = row["id"]
                cursor.execute(
                    """
                    UPDATE plane_instances
                    SET status = 'CHECKED_OUT', usecase = ?, removed_by = ?
                    WHERE id = ?
                    """,
                    (usecase, str(user_id), plane_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO plane_instances (war_number, airfield_id, plane_type, added_by, status, usecase, removed_by)
                    VALUES (?, ?, ?, 'UNREGISTERED', 'CHECKED_OUT', ?, ?)
                    """,
                    (war_number, airfield_id, plane_type, usecase, str(user_id))
                )
            conn.commit()
            return True

    @staticmethod
    def complete_flight(user_id: str, status: str, kills: int, target_killed: str, by_type: dict = None):
        by_type = by_type or {}
        flight = AirfieldRepository.get_user_active_flight(user_id)
        if not flight:
            return None

        with get_db() as conn:
            conn.execute(
                """
                UPDATE plane_instances
                SET status = ?, kills = ?, target_killed = ?,
                    toxot_kills = ?, harpy_kills = ?, myrmidon_kills = ?, pegasus_kills = ?, tzykalia_kills = ?
                WHERE id = ?
                """,
                (status, kills, target_killed,
                 by_type.get("toxot", 0), by_type.get("harpy", 0), by_type.get("myrmidon", 0),
                 by_type.get("pegasus", 0), by_type.get("tzykalia", 0), flight["id"])
            )
            conn.commit()
        return flight

    @staticmethod
    def get_kill_board(war_number: int = None, limit: int = 10):
        """Finished sorties of a war: totals per aircraft type, plus a pilot leaderboard by total kills."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            totals = conn.execute(
                """
                SELECT COUNT(*) AS sorties,
                       COALESCE(SUM(status = 'Loss'), 0) AS losses,
                       COALESCE(SUM(toxot_kills), 0) AS toxot,
                       COALESCE(SUM(harpy_kills), 0) AS harpy,
                       COALESCE(SUM(myrmidon_kills), 0) AS myrmidon,
                       COALESCE(SUM(pegasus_kills), 0) AS pegasus,
                       COALESCE(SUM(tzykalia_kills), 0) AS tzykalia
                FROM plane_instances WHERE war_number = ? AND status IN ('Returned', 'Loss')
                """,
                (war_number,)
            ).fetchone()
            pilots = conn.execute(
                """
                SELECT removed_by AS user_id, SUM(kills) AS kills, COUNT(*) AS sorties
                FROM plane_instances
                WHERE war_number = ? AND status IN ('Returned', 'Loss') AND removed_by IS NOT NULL
                GROUP BY removed_by HAVING kills > 0
                ORDER BY kills DESC, sorties ASC LIMIT ?
                """,
                (war_number, limit)
            ).fetchall()
        return {"totals": totals, "pilots": pilots}

    @staticmethod
    def set_config(key: str, value: str):
        settings.set_setting(key, value)

    @staticmethod
    def get_config(key: str) -> str | None:
        return settings.get_setting(key)
