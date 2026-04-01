from typing import List, Optional
from database import db_cursor
from models import AdAccount


def list_accounts(active_only=False) -> List[AdAccount]:
    with db_cursor() as cur:
        if active_only:
            cur.execute("SELECT * FROM ad_accounts WHERE active=1 ORDER BY owner, name")
        else:
            cur.execute("SELECT * FROM ad_accounts ORDER BY owner, name")
        return [_row(r) for r in cur.fetchall()]


def get_account(aid: int) -> Optional[AdAccount]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM ad_accounts WHERE id=?", (aid,))
        row = cur.fetchone()
        return _row(row) if row else None


def create_account(data: dict) -> int:
    with db_cursor(commit=True) as cur:
        cur.execute("""INSERT INTO ad_accounts
            (name,platform,owner,rt_campaign_id,fb_access_token,fb_ad_account_id,fb_pixel_id,
             google_ads_account_id,google_mcc_id,google_developer_token,google_client_id,
             google_client_secret,google_refresh_token,active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["platform"], data.get("owner",""),
             data.get("rt_campaign_id",""),
             data.get("fb_access_token",""), data.get("fb_ad_account_id",""), data.get("fb_pixel_id",""),
             data.get("google_ads_account_id",""), data.get("google_mcc_id",""),
             data.get("google_developer_token",""), data.get("google_client_id",""),
             data.get("google_client_secret",""), data.get("google_refresh_token",""),
             1 if data.get("active", True) else 0))
        return cur.lastrowid


def update_account(aid: int, data: dict):
    with db_cursor(commit=True) as cur:
        cur.execute("""UPDATE ad_accounts SET
            name=?,platform=?,owner=?,rt_campaign_id=?,
            fb_access_token=?,fb_ad_account_id=?,fb_pixel_id=?,
            google_ads_account_id=?,google_mcc_id=?,google_developer_token=?,
            google_client_id=?,google_client_secret=?,google_refresh_token=?,active=?
            WHERE id=?""",
            (data["name"], data["platform"], data.get("owner",""),
             data.get("rt_campaign_id",""),
             data.get("fb_access_token",""), data.get("fb_ad_account_id",""), data.get("fb_pixel_id",""),
             data.get("google_ads_account_id",""), data.get("google_mcc_id",""),
             data.get("google_developer_token",""), data.get("google_client_id",""),
             data.get("google_client_secret",""), data.get("google_refresh_token",""),
             1 if data.get("active", True) else 0, aid))


def delete_account(aid: int):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM ad_accounts WHERE id=?", (aid,))


def _row(r) -> AdAccount:
    return AdAccount(
        id=r["id"], name=r["name"], platform=r["platform"], owner=r["owner"],
        rt_campaign_id=r["rt_campaign_id"],
        fb_access_token=r["fb_access_token"], fb_ad_account_id=r["fb_ad_account_id"],
        fb_pixel_id=r["fb_pixel_id"],
        google_ads_account_id=r["google_ads_account_id"], google_mcc_id=r["google_mcc_id"],
        google_developer_token=r["google_developer_token"], google_client_id=r["google_client_id"],
        google_client_secret=r["google_client_secret"], google_refresh_token=r["google_refresh_token"],
        active=bool(r["active"]), created_at=r["created_at"])
