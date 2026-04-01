from typing import List, Optional
from database import db_cursor
from models import TeamMember


def list_members() -> List[TeamMember]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM team_members ORDER BY name")
        return [_row_to_member(r) for r in cur.fetchall()]


def get_member(member_id: int) -> Optional[TeamMember]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM team_members WHERE id = ?", (member_id,))
        row = cur.fetchone()
        return _row_to_member(row) if row else None


def create_member(name: str, email: str, **tokens) -> int:
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO team_members (name, email,
                fb_access_token, fb_ad_account_id,
                google_developer_token, google_client_id, google_client_secret,
                google_refresh_token, google_customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email,
            tokens.get("fb_access_token", ""),
            tokens.get("fb_ad_account_id", ""),
            tokens.get("google_developer_token", ""),
            tokens.get("google_client_id", ""),
            tokens.get("google_client_secret", ""),
            tokens.get("google_refresh_token", ""),
            tokens.get("google_customer_id", ""),
        ))
        return cur.lastrowid


def update_member(member_id: int, name: str, email: str, **tokens):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE team_members
            SET name=?, email=?,
                fb_access_token=?, fb_ad_account_id=?,
                google_developer_token=?, google_client_id=?, google_client_secret=?,
                google_refresh_token=?, google_customer_id=?
            WHERE id=?
        """, (
            name, email,
            tokens.get("fb_access_token", ""),
            tokens.get("fb_ad_account_id", ""),
            tokens.get("google_developer_token", ""),
            tokens.get("google_client_id", ""),
            tokens.get("google_client_secret", ""),
            tokens.get("google_refresh_token", ""),
            tokens.get("google_customer_id", ""),
            member_id,
        ))


def delete_member(member_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM team_members WHERE id = ?", (member_id,))


def _row_to_member(row) -> TeamMember:
    return TeamMember(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        fb_access_token=row["fb_access_token"],
        fb_ad_account_id=row["fb_ad_account_id"],
        google_developer_token=row["google_developer_token"],
        google_client_id=row["google_client_id"],
        google_client_secret=row["google_client_secret"],
        google_refresh_token=row["google_refresh_token"],
        google_customer_id=row["google_customer_id"],
        created_at=row["created_at"],
    )
