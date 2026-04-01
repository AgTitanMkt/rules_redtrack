"""
Platform Executors — execute pause/restart/scale actions directly
on Meta Graph API and Google Ads API using each member's tokens.
"""

import json
import requests
from typing import Dict, Any
from models import TeamMember


# ═══════════════════════════════════════════════════════════════════
#  META / FACEBOOK ADS  — Graph API v21.0
# ═══════════════════════════════════════════════════════════════════

GRAPH_API = "https://graph.facebook.com/v21.0"


def fb_pause_object(member: TeamMember, object_type: str, platform_id: str) -> Dict[str, Any]:
    """Pause a campaign/adset/ad on Meta Ads."""
    url = f"{GRAPH_API}/{platform_id}"
    resp = requests.post(url, params={
        "access_token": member.fb_access_token,
        "status": "PAUSED",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fb_restart_object(member: TeamMember, object_type: str, platform_id: str) -> Dict[str, Any]:
    """Restart (activate) a campaign/adset/ad on Meta Ads."""
    url = f"{GRAPH_API}/{platform_id}"
    resp = requests.post(url, params={
        "access_token": member.fb_access_token,
        "status": "ACTIVE",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fb_scale_budget(member: TeamMember, object_type: str, platform_id: str,
                    direction: str, percent: float) -> Dict[str, Any]:
    """
    Scale daily budget up or down by a percentage.
    Works on campaigns and adsets (they have daily_budget).
    """
    # First get current budget
    url = f"{GRAPH_API}/{platform_id}"
    resp = requests.get(url, params={
        "access_token": member.fb_access_token,
        "fields": "daily_budget,name",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    current_budget = int(data.get("daily_budget", 0))  # in cents
    if current_budget <= 0:
        return {"error": "No daily_budget found", "data": data}

    multiplier = 1 + (percent / 100) if direction == "up" else 1 - (percent / 100)
    new_budget = max(100, int(current_budget * multiplier))  # minimum $1

    resp2 = requests.post(url, params={
        "access_token": member.fb_access_token,
        "daily_budget": new_budget,
    }, timeout=30)
    resp2.raise_for_status()
    return {
        "old_budget": current_budget,
        "new_budget": new_budget,
        "direction": direction,
        "percent": percent,
        "result": resp2.json(),
    }


# ═══════════════════════════════════════════════════════════════════
#  GOOGLE ADS  — REST API v18
# ═══════════════════════════════════════════════════════════════════

GOOGLE_ADS_API = "https://googleads.googleapis.com/v18"
GOOGLE_OAUTH_URL = "https://oauth2.googleapis.com/token"


def _google_get_access_token(member: TeamMember) -> str:
    """Exchange refresh token for access token."""
    resp = requests.post(GOOGLE_OAUTH_URL, data={
        "client_id": member.google_client_id,
        "client_secret": member.google_client_secret,
        "refresh_token": member.google_refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _google_headers(member: TeamMember, access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "developer-token": member.google_developer_token,
        "Content-Type": "application/json",
    }


def google_pause_campaign(member: TeamMember, platform_id: str) -> Dict[str, Any]:
    """Pause a Google Ads campaign by resource name."""
    access_token = _google_get_access_token(member)
    customer_id = member.google_customer_id.replace("-", "")

    url = f"{GOOGLE_ADS_API}/customers/{customer_id}/campaigns:mutate"
    body = {
        "operations": [{
            "updateMask": "status",
            "update": {
                "resourceName": platform_id,
                "status": "PAUSED",
            }
        }]
    }
    resp = requests.post(url, headers=_google_headers(member, access_token),
                         json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def google_restart_campaign(member: TeamMember, platform_id: str) -> Dict[str, Any]:
    """Enable a Google Ads campaign."""
    access_token = _google_get_access_token(member)
    customer_id = member.google_customer_id.replace("-", "")

    url = f"{GOOGLE_ADS_API}/customers/{customer_id}/campaigns:mutate"
    body = {
        "operations": [{
            "updateMask": "status",
            "update": {
                "resourceName": platform_id,
                "status": "ENABLED",
            }
        }]
    }
    resp = requests.post(url, headers=_google_headers(member, access_token),
                         json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def google_pause_adgroup(member: TeamMember, platform_id: str) -> Dict[str, Any]:
    """Pause a Google Ads ad group."""
    access_token = _google_get_access_token(member)
    customer_id = member.google_customer_id.replace("-", "")

    url = f"{GOOGLE_ADS_API}/customers/{customer_id}/adGroups:mutate"
    body = {
        "operations": [{
            "updateMask": "status",
            "update": {
                "resourceName": platform_id,
                "status": "PAUSED",
            }
        }]
    }
    resp = requests.post(url, headers=_google_headers(member, access_token),
                         json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════
#  Unified executor
# ═══════════════════════════════════════════════════════════════════

def execute_action(
    member: TeamMember,
    traffic_channel: str,
    object_type: str,
    platform_id: str,
    action: str,
    scale_value: float = None,
) -> Dict[str, Any]:
    """
    Execute an action on the native platform.
    Returns the API response dict.
    """
    if traffic_channel == "facebook":
        if action == "pause":
            return fb_pause_object(member, object_type, platform_id)
        elif action == "pause_restart":
            return fb_pause_object(member, object_type, platform_id)
        elif action == "scale_budget_up":
            return fb_scale_budget(member, object_type, platform_id, "up", scale_value or 10)
        elif action == "scale_budget_down":
            return fb_scale_budget(member, object_type, platform_id, "down", scale_value or 10)

    elif traffic_channel == "google":
        if action in ("pause", "pause_restart"):
            if object_type == "adgroup":
                return google_pause_adgroup(member, platform_id)
            else:
                return google_pause_campaign(member, platform_id)
        elif action == "scale_budget_up":
            return {"note": "Google budget scaling requires Campaign Budget mutate — implement per needs"}
        elif action == "scale_budget_down":
            return {"note": "Google budget scaling requires Campaign Budget mutate — implement per needs"}

    return {"status": "no_executor", "channel": traffic_channel, "action": action}
