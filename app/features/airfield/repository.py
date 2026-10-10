from app.core.database import get_db

class AirfieldRepository:
    @staticmethod
    def get_active_war() -> int:
        val = AirfieldRepository.get_config("active_war")
        return int(val) if val else 1

    @staticmethod
    def set_active_war(war_number: int):
        AirfieldRepository.set_config("active_war", str(war_number))

    @staticmethod
    def add_airfield(name: str, code: str, location: str, thread_id: str = None):
        war_number = AirfieldRepository.get_active_war()
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
        war_number = AirfieldRepository.get_active_war()
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
        if war_number is None:
            war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            conn.execute(
                "UPDATE airfields SET status = 'DELETED' WHERE code = ? AND war_number = ? AND status = 'ACTIVE'",
                (code.upper(), war_number)
            )
            # Retire leftover stock so it can't resurface if the code is reused by a new depot.
            conn.execute(
                "UPDATE plane_instances SET status = 'DEPOT_DELETED' "
                "WHERE airfield_code = ? AND war_number = ? AND status = 'IN_STOCK'",
                (code.upper(), war_number)
            )
            conn.commit()

    @staticmethod
    def get_airfields(war_number: int = None, status: str = 'ACTIVE'):
        if war_number is None:
            war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code, name, location, thread_id, war_number, status FROM airfields WHERE war_number = ? AND status = ? ORDER BY name ASC",
                (war_number, status)
            )
            return cursor.fetchall()

    @staticmethod
    def get_all_war_airfields():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code, name, location, thread_id, war_number, status FROM airfields")
            return cursor.fetchall()

    @staticmethod
    def get_depot(code: str, war_number: int = None):
        if war_number is None:
            war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT code, name, location, thread_id, war_number, status FROM airfields "
                "WHERE code = ? AND war_number = ? ORDER BY (status = 'ACTIVE') DESC, id DESC LIMIT 1",
                (code.upper(), war_number)
            )
            return cursor.fetchone()

    @staticmethod
    def add_plane(airfield_code: str, plane_type: str, user_id: str):
        war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plane_instances (war_number, airfield_code, plane_type, added_by, status)
                VALUES (?, ?, ?, ?, 'IN_STOCK')
                """,
                (war_number, airfield_code.upper(), plane_type, user_id)
            )
            conn.commit()

    @staticmethod
    def get_available_planes(airfield_code: str):
        war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT plane_type, COUNT(*) as count
                FROM plane_instances
                WHERE war_number = ? AND airfield_code = ? AND status = 'IN_STOCK'
                GROUP BY plane_type
                HAVING count > 0
                """,
                (war_number, airfield_code.upper())
            )
            return cursor.fetchall()

    @staticmethod
    def get_stock_summary(airfield_code: str):
        war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT plane_type, COUNT(*) as count
                FROM plane_instances
                WHERE war_number = ? AND airfield_code = ? AND status = 'IN_STOCK'
                GROUP BY plane_type
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
                SELECT id, war_number, airfield_code, plane_type, usecase
                FROM plane_instances
                WHERE removed_by = ? AND status = 'CHECKED_OUT'
                LIMIT 1
                """,
                (str(user_id),)
            )
            return cursor.fetchone()

    @staticmethod
    def checkout_plane(airfield_code: str, plane_type: str, usecase: str, user_id: str) -> bool:
        if AirfieldRepository.get_user_active_flight(user_id):
            return False

        war_number = AirfieldRepository.get_active_war()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM plane_instances
                WHERE war_number = ? AND airfield_code = ? AND plane_type = ? AND status = 'IN_STOCK'
                LIMIT 1
                """,
                (war_number, airfield_code.upper(), plane_type)
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
                    INSERT INTO plane_instances (war_number, airfield_code, plane_type, added_by, status, usecase, removed_by)
                    VALUES (?, ?, ?, 'UNREGISTERED', 'CHECKED_OUT', ?, ?)
                    """,
                    (war_number, airfield_code.upper(), plane_type, usecase, str(user_id))
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
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    @staticmethod
    def get_config(key: str) -> str | None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None