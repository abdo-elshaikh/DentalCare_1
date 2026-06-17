import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.sqlite3"

VALID_STATUSES = {"new", "processing", "done", "needs_attention", "failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_identifier TEXT NOT NULL,
                patient_age INTEGER,
                patient_sex TEXT,
                analysis_type TEXT NOT NULL,
                status TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                px_to_mm REAL NOT NULL DEFAULT 1.0,
                ethnic_profile TEXT NOT NULL DEFAULT 'Caucasian',
                filename TEXT,
                landmarks_json TEXT NOT NULL DEFAULT '[]',
                analysis_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_patients (
                id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL DEFAULT '',
                date_of_birth TEXT,
                gender TEXT,
                phone TEXT,
                email TEXT,
                medical_record_no TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_patients_medical_record_no ON ai_patients(medical_record_no)")


def _loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return fallback


def row_to_case(row: sqlite3.Row, include_payload: bool = False) -> Dict[str, Any]:
    case = {
        "id": row["id"],
        "patient_identifier": row["patient_identifier"],
        "patient_age": row["patient_age"],
        "patient_sex": row["patient_sex"],
        "analysis_type": row["analysis_type"],
        "status": row["status"],
        "comment": row["comment"],
        "px_to_mm": row["px_to_mm"],
        "ethnic_profile": row["ethnic_profile"],
        "filename": row["filename"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_payload:
        case["landmarks"] = _loads(row["landmarks_json"], [])
        case["analysis"] = _loads(row["analysis_json"], {})
    return case


def create_case(
    patient_identifier: str,
    analysis_type: str,
    landmarks: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    *,
    patient_age: Optional[int] = None,
    patient_sex: Optional[str] = None,
    status: str = "done",
    comment: str = "",
    px_to_mm: float = 1.0,
    ethnic_profile: str = "Caucasian",
    filename: Optional[str] = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    if not patient_identifier.strip():
        raise ValueError("patient_identifier is required")

    now = utc_now()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO cases (
                patient_identifier, patient_age, patient_sex, analysis_type,
                status, comment, px_to_mm, ethnic_profile, filename,
                landmarks_json, analysis_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_identifier,
                patient_age,
                patient_sex,
                analysis_type,
                status,
                comment,
                px_to_mm,
                ethnic_profile,
                filename,
                json.dumps(landmarks),
                json.dumps(analysis),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_case(row, include_payload=True)


def list_cases(
    *,
    status: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 100,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    clauses = []
    params: List[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if query:
        clauses.append("(patient_identifier LIKE ? OR comment LIKE ? OR analysis_type LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 500)))
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM cases {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [row_to_case(row, include_payload=False) for row in rows]


def get_case(case_id: int, *, db_path: Path | str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return row_to_case(row, include_payload=True) if row else None


def update_case(
    case_id: int,
    *,
    status: Optional[str] = None,
    comment: Optional[str] = None,
    landmarks: Optional[List[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    updates = []
    params: List[Any] = []
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        updates.append("status = ?")
        params.append(status)
    if comment is not None:
        updates.append("comment = ?")
        params.append(comment)
    if landmarks is not None:
        updates.append("landmarks_json = ?")
        params.append(json.dumps(landmarks))
    if analysis is not None:
        updates.append("analysis_json = ?")
        params.append(json.dumps(analysis))
    if not updates:
        return get_case(case_id, db_path=db_path)

    updates.append("updated_at = ?")
    params.append(utc_now())
    params.append(case_id)

    with connect(db_path) as conn:
        conn.execute(f"UPDATE cases SET {', '.join(updates)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return row_to_case(row, include_payload=True) if row else None


def delete_case(case_id: int, *, db_path: Path | str = DEFAULT_DB_PATH) -> bool:
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        return cur.rowcount > 0


def row_to_patient(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "dateOfBirth": row["date_of_birth"],
        "gender": row["gender"],
        "phone": row["phone"],
        "email": row["email"],
        "medicalRecordNo": row["medical_record_no"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def upsert_patient(
    *,
    first_name: str,
    medical_record_no: str,
    last_name: str = "",
    date_of_birth: Optional[str] = None,
    gender: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    first_name = (first_name or "").strip()
    medical_record_no = (medical_record_no or "").strip()
    if not first_name:
        raise ValueError("firstName is required")
    if not medical_record_no:
        raise ValueError("medicalRecordNo is required")

    now = utc_now()
    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM ai_patients WHERE medical_record_no = ?",
            (medical_record_no,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE ai_patients
                SET first_name = ?, last_name = ?, date_of_birth = ?, gender = ?,
                    phone = ?, email = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    first_name,
                    last_name or "",
                    date_of_birth,
                    gender,
                    phone,
                    email,
                    now,
                    existing["id"],
                ),
            )
            row = conn.execute("SELECT * FROM ai_patients WHERE id = ?", (existing["id"],)).fetchone()
        else:
            patient_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO ai_patients (
                    id, first_name, last_name, date_of_birth, gender, phone,
                    email, medical_record_no, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    first_name,
                    last_name or "",
                    date_of_birth,
                    gender,
                    phone,
                    email,
                    medical_record_no,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM ai_patients WHERE id = ?", (patient_id,)).fetchone()

    return row_to_patient(row)
