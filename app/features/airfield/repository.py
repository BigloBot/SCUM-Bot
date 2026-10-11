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
    def complete_flight(user_id: str, status: str, destination_airfield_id: int = None):
        """
        Closes the pilot's active flight. The sortie row stays as history. A returned aircraft goes back into
        stock as a fresh in-stock row at the destination depot (the depot it left from unless a transport
        names another). Raises ValueError if the destination isn't an active depot of the current war.
        """
        flight = AirfieldRepository.get_user_active_flight(user_id)
        if not flight:
            return None

        war_number = settings.get_active_war()
        destination = destination_airfield_id if destination_airfield_id is not None else flight["airfield_id"]
        with get_db() as conn:
            if status == "Returned" and AirfieldRepository._active_depot_id(conn, destination, war_number) is None:
                raise ValueError("destination depot is not active")
            conn.execute(
                """
                UPDATE plane_instances
                SET status = ?, completed_at = CURRENT_TIMESTAMP, destination_airfield_id = ?
                WHERE id = ?
                """,
                (status, destination if status == "Returned" else None, flight["id"])
            )
            if status == "Returned":
                conn.execute(
                    """
                    INSERT INTO plane_instances (war_number, airfield_id, plane_type, added_by, status)
                    VALUES (?, ?, ?, 'RETURNED', 'IN_STOCK')
                    """,
                    (war_number, destination, flight["plane_type"])
                )
            conn.commit()
        return flight

    @staticmethod
    def add_kill_report(user_id: str, by_type: dict) -> int:
        """Records kills reported by a pilot, independent of any flight. Returns the total reported."""
        counts = {k: max(0, int(by_type.get(k, 0))) for k in ("toxot", "harpy", "myrmidon", "pegasus", "tzykalia")}
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO kill_reports (war_number, user_id, toxot, harpy, myrmidon, pegasus, tzykalia)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (settings.get_active_war(), str(user_id), counts["toxot"], counts["harpy"],
                 counts["myrmidon"], counts["pegasus"], counts["tzykalia"])
            )
            conn.commit()
        return sum(counts.values())

    @staticmethod
    def get_kill_board(war_number: int = None, limit: int = 10):
        """Kill reports of a war: totals per aircraft type, plus a pilot leaderboard by total kills."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            totals = conn.execute(
                """
                SELECT COUNT(*) AS reports,
                       COALESCE(SUM(toxot), 0) AS toxot, COALESCE(SUM(harpy), 0) AS harpy,
                       COALESCE(SUM(myrmidon), 0) AS myrmidon, COALESCE(SUM(pegasus), 0) AS pegasus,
                       COALESCE(SUM(tzykalia), 0) AS tzykalia
                FROM kill_reports WHERE war_number = ?
                """,
                (war_number,)
            ).fetchone()
            pilots = conn.execute(
                """
                SELECT user_id, SUM(toxot + harpy + myrmidon + pegasus + tzykalia) AS kills,
                       SUM(toxot) AS toxot, SUM(harpy) AS harpy, SUM(myrmidon) AS myrmidon,
                       SUM(pegasus) AS pegasus, SUM(tzykalia) AS tzykalia
                FROM kill_reports WHERE war_number = ?
                GROUP BY user_id HAVING kills > 0 ORDER BY kills DESC LIMIT ?
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
