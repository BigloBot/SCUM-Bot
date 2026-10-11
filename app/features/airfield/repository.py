from app.core import settings
from app.core.database import get_db

class AirfieldRepository:
    @staticmethod
    def _active_depot_id(conn, airfield_code: str, war_number: int) -> int | None:
        """Resolves a depot code to the id of the ACTIVE airfield row in the given war."""
        row = conn.execute(
            "SELECT id FROM airfields WHERE code = ? AND war_number = ? AND status = 'ACTIVE'",
            (airfield_code.upper(), war_number)
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
    def check_duplicate(name: str, code: str) -> str | None:
        """Checks if a depot name or passcode already exists active within the current war."""
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name, code FROM airfields
                WHERE (name = ? OR code = ?) AND war_number = ? AND status = 'ACTIVE'
                """,
                (name.upper(), code.upper(), war_number)
            )
            row = cursor.fetchone()
            if row:
                if row["name"] == name.upper():
                    return "name"
                return "code"
        return None

    @staticmethod
    def delete_airfield(code: str, war_number: int = None):
        """Soft delete only: the row and all of its plane history are kept for reporting."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            conn.execute(
                "UPDATE airfields SET status = 'DELETED' WHERE code = ? AND war_number = ? AND status = 'ACTIVE'",
                (code.upper(), war_number)
            )
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
    def get_depot(code: str, war_number: int = None):
        """Looks a depot up by code within a war, preferring the ACTIVE row over deleted ones."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, code, name, location, thread_id, war_number, status FROM airfields "
                "WHERE code = ? AND war_number = ? ORDER BY (status = 'ACTIVE') DESC, id DESC LIMIT 1",
                (code.upper(), war_number)
            )
            return cursor.fetchone()

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
    def add_plane(airfield_code: str, plane_type: str, user_id: str) -> bool:
        war_number = settings.get_active_war()
        with get_db() as conn:
            airfield_id = AirfieldRepository._active_depot_id(conn, airfield_code, war_number)
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
    def get_available_planes(airfield_code: str):
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.plane_type, COUNT(*) as count
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE a.war_number = ? AND a.code = ? AND a.status = 'ACTIVE' AND p.status = 'IN_STOCK'
                GROUP BY p.plane_type
                HAVING count > 0
                """,
                (war_number, airfield_code.upper())
            )
            return cursor.fetchall()

    @staticmethod
    def get_stock_summary(airfield_code: str):
        war_number = settings.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.plane_type, COUNT(*) as count
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE a.war_number = ? AND a.code = ? AND a.status = 'ACTIVE' AND p.status = 'IN_STOCK'
                GROUP BY p.plane_type
                """,
                (war_number, airfield_code.upper())
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
    def checkout_plane(airfield_code: str, plane_type: str, usecase: str, user_id: str) -> bool:
        if AirfieldRepository.get_user_active_flight(user_id):
            return False

        war_number = settings.get_active_war()
        with get_db() as conn:
            airfield_id = AirfieldRepository._active_depot_id(conn, airfield_code, war_number)
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
    def complete_flight(user_id: str, status: str, kills: int, target_killed: str):
        flight = AirfieldRepository.get_user_active_flight(user_id)
        if not flight:
            return None

        plane_id = flight["id"]
        with get_db() as conn:
            conn.execute(
                """
                UPDATE plane_instances
                SET status = ?, kills = ?, target_killed = ?
                WHERE id = ?
                """,
                (status, kills, target_killed, plane_id)
            )
            conn.commit()
        return flight

    @staticmethod
    def set_config(key: str, value: str):
        settings.set_setting(key, value)

    @staticmethod
    def get_config(key: str) -> str | None:
        return settings.get_setting(key)
