from app.core import settings
from app.core.config import PlaneType, config
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
    def get_aircraft_types() -> list[PlaneType]:
        """Our own aircraft, in display order (see warden_planes in config.yaml). `label` is what planes store."""
        return config.features.airfield.warden_planes

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
    def get_total_stock():
        """Aircraft in stock across every active depot of the active war: one row per stored plane_type."""
        war_number = settings.get_active_war()
        with get_db() as conn:
            return conn.execute(
                """
                SELECT p.plane_type, COUNT(*) AS count
                FROM plane_instances p
                JOIN airfields a ON a.id = p.airfield_id
                WHERE a.war_number = ? AND a.status = 'ACTIVE' AND p.status = 'IN_STOCK'
                GROUP BY p.plane_type
                """,
                (war_number,)
            ).fetchall()

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
                WHERE airfield_id = ? AND (plane_type = ? OR plane_type LIKE ? || ' (%') AND status = 'IN_STOCK'
                LIMIT 1
                """,
                (airfield_id, plane_type, plane_type)
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
    def get_kill_types() -> list[PlaneType]:
        """The configured kill types, in display order (colonial_planes in config.yaml)."""
        return list(config.features.airfield.kill_types)

    @staticmethod
    def get_user_active_flight_in_war(user_id: str, war_number: int = None):
        """Return the pilot's active flight for one war, if any."""
        war_number = war_number if war_number is not None else settings.get_active_war()
        with get_db() as conn:
            return conn.execute(
                """
                SELECT id, plane_type, status, usecase
                FROM plane_instances
                WHERE war_number = ? AND removed_by = ? AND status = 'CHECKED_OUT'
                ORDER BY id DESC LIMIT 1
                """,
                (war_number, str(user_id)),
            ).fetchone()

    @staticmethod
    def get_user_latest_completed_flight(user_id: str, war_number: int = None):
        """Return the pilot's most recently completed flight for one war, if any."""
        war_number = war_number if war_number is not None else settings.get_active_war()
        with get_db() as conn:
            return conn.execute(
                """
                SELECT id, plane_type, status, usecase, completed_at
                FROM plane_instances
                WHERE war_number = ? AND removed_by = ? AND status IN ('Returned', 'Loss')
                ORDER BY COALESCE(completed_at, created_at) DESC, id DESC LIMIT 1
                """,
                (war_number, str(user_id)),
            ).fetchone()

    @staticmethod
    def add_kill_report(user_id: str, counts: dict[str, int], flight_id: int | None = None) -> int | None:
        """Record valid kills, optionally binding them to a flight owned by this pilot in the active war."""
        counts = {key: int(n) for key, n in counts.items() if key in config.colonial_planes_by_key and int(n) > 0}
        if not counts:
            return None

        war_number = settings.get_active_war()
        with get_db() as conn:
            if flight_id is not None:
                flight = conn.execute(
                    "SELECT id FROM plane_instances WHERE id = ? AND war_number = ? AND removed_by = ?",
                    (flight_id, war_number, str(user_id)),
                ).fetchone()
                if flight is None:
                    raise ValueError("flight is no longer available for this report")
            cursor = conn.execute(
                "INSERT INTO kill_reports (war_number, user_id, flight_id) VALUES (?, ?, ?)",
                (war_number, str(user_id), flight_id),
            )
            report_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO kill_report_items (report_id, kill_type, count) VALUES (?, ?, ?)",
                [(report_id, key, n) for key, n in counts.items()]
            )
            conn.commit()
        return report_id

    @staticmethod
    def get_pilot_kill_entries(user_id: str, war_number: int = None, limit: int = 25):
        """A pilot's kill report entries for a war (one row per report and kill type), newest first."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            return conn.execute(
                """
                SELECT r.id AS report_id, i.kill_type, i.count, r.created_at
                FROM kill_reports r JOIN kill_report_items i ON i.report_id = r.id
                WHERE r.war_number = ? AND r.user_id = ?
                ORDER BY r.id DESC, i.kill_type
                LIMIT ?
                """,
                (war_number, str(user_id), limit)
            ).fetchall()

    @staticmethod
    def set_kill_entry_count(report_id: int, kill_type: str, count: int) -> bool:
        """Corrects how many of a kill type a report holds. False if that entry no longer exists."""
        if count < 1:
            raise ValueError("count must be at least 1")
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE kill_report_items SET count = ? WHERE report_id = ? AND kill_type = ?",
                (count, report_id, kill_type)
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_kill_entry(report_id: int, kill_type: str) -> bool:
        """Removes a kill report entry (and its report once it has no entries left). False if already gone."""
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM kill_report_items WHERE report_id = ? AND kill_type = ?",
                (report_id, kill_type)
            )
            conn.execute(
                "DELETE FROM kill_reports WHERE id = ? AND NOT EXISTS "
                "(SELECT 1 FROM kill_report_items WHERE report_id = ?)",
                (report_id, report_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_kill_board(war_number: int = None, pilot_limit: int = 10):
        """Kill reports of a war: totals per kill type and a pilot leaderboard with each pilot's kills by type."""
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT r.user_id, i.kill_type, SUM(i.count) AS kills
                FROM kill_report_items i JOIN kill_reports r ON r.id = i.report_id
                WHERE r.war_number = ?
                GROUP BY r.user_id, i.kill_type
                """,
                (war_number,)
            ).fetchall()

        kill_config = config.features.airfield
        label = kill_config.kill_type_label  # a type removed from the config still shows under its stored key
        position = kill_config.kill_type_position

        totals = {t.key: 0 for t in kill_config.kill_types}
        pilots: dict[str, dict] = {}
        for row in rows:
            totals[row["kill_type"]] = totals.get(row["kill_type"], 0) + row["kills"]
            pilot = pilots.setdefault(row["user_id"], {"user_id": row["user_id"], "kills": 0, "by_type": []})
            pilot["kills"] += row["kills"]
            pilot["by_type"].append((position(row["kill_type"]), label(row["kill_type"]), row["kills"]))
        leaderboard = sorted(pilots.values(), key=lambda p: -p["kills"])[:pilot_limit]
        for pilot in leaderboard:
            pilot["by_type"] = [(name, n) for _, name, n in sorted(pilot["by_type"])]
        return {
            "types": [(label(key), n) for key, n in totals.items()],
            "total": sum(totals.values()),
            "pilots": leaderboard,
        }

    @staticmethod
    def get_pilot_stats(war_number: int = None) -> list[dict]:
        """
        Per pilot for a war: kills (from kill reports), flights (finished sorties, losses included) and deaths
        (sorties logged as a Loss). Pilots with only kills or only flights are included.
        """
        if war_number is None:
            war_number = settings.get_active_war()
        with get_db() as conn:
            kill_rows = conn.execute(
                """
                SELECT r.user_id, SUM(i.count) AS kills
                FROM kill_reports r JOIN kill_report_items i ON i.report_id = r.id
                WHERE r.war_number = ?
                GROUP BY r.user_id
                """,
                (war_number,)
            ).fetchall()
            flight_rows = conn.execute(
                """
                SELECT removed_by AS user_id, COUNT(*) AS flights, SUM(status = 'Loss') AS deaths
                FROM plane_instances
                WHERE war_number = ? AND status IN ('Returned', 'Loss') AND removed_by IS NOT NULL
                GROUP BY removed_by
                """,
                (war_number,)
            ).fetchall()

        pilots: dict[str, dict] = {}
        for row in kill_rows:
            pilots.setdefault(row["user_id"], {"user_id": row["user_id"], "kills": 0, "flights": 0, "deaths": 0})
            pilots[row["user_id"]]["kills"] = row["kills"]
        for row in flight_rows:
            pilots.setdefault(row["user_id"], {"user_id": row["user_id"], "kills": 0, "flights": 0, "deaths": 0})
            pilots[row["user_id"]]["flights"] = row["flights"]
            pilots[row["user_id"]]["deaths"] = row["deaths"]
        return list(pilots.values())

    # added_by values that are not a pilot adding stock: aircraft that came back from a flight, and
    # aircraft checked out that were never registered in stock.
    _NOT_PRODUCTION = ("RETURNED", "UNREGISTERED")

    @staticmethod
    def get_production_stats(war_number: int = None, producer_limit: int = 10) -> dict:
        """
        Aircraft added to depot stock in a war (whatever happened to them since): totals per stored plane_type
        and the pilots who added the most. Returned aircraft and unregistered checkouts are not production.
        """
        if war_number is None:
            war_number = settings.get_active_war()
        not_production = AirfieldRepository._NOT_PRODUCTION
        with get_db() as conn:
            by_type = conn.execute(
                """
                SELECT plane_type, COUNT(*) AS count FROM plane_instances
                WHERE war_number = ? AND added_by NOT IN (?, ?)
                GROUP BY plane_type
                """,
                (war_number, *not_production)
            ).fetchall()
            producers = conn.execute(
                """
                SELECT added_by AS user_id, COUNT(*) AS count FROM plane_instances
                WHERE war_number = ? AND added_by NOT IN (?, ?)
                GROUP BY added_by ORDER BY count DESC, added_by LIMIT ?
                """,
                (war_number, *not_production, producer_limit)
            ).fetchall()
        return {"by_type": by_type, "producers": producers, "total": sum(r["count"] for r in by_type)}

    @staticmethod
    def set_config(key: str, value: str):
        settings.set_setting(key, value)

    @staticmethod
    def get_config(key: str) -> str | None:
        return settings.get_setting(key)
