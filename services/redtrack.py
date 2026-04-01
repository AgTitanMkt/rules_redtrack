"""
RedTrack Data Source — fetches campaign metrics from RedTrack API.
Uses a single global API key (configured in Settings).
Falls back to mock data if key is not set.
"""

import os
import requests
from typing import List
from models import CampaignData

REDTRACK_BASE_URL = os.getenv("REDTRACK_BASE_URL", "https://api.redtrack.io")


class RedTrackClient:
    def __init__(self, api_key: str = ""):
        self.base_url = REDTRACK_BASE_URL.rstrip("/")
        self.api_key = api_key

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def fetch_report(self, member_id: int = 0) -> List[CampaignData]:
        if not self.api_key:
            raise RuntimeError("No RedTrack API key")

        url = f"{self.base_url}/report"
        payload = {
            "group_by": ["campaign"],
            "metrics": ["cost", "revenue", "profit", "conversions", "clicks", "impressions"],
            "limit": 500,
        }
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("rows", data) if isinstance(data, dict) else data
        results: List[CampaignData] = []

        for row in rows:
            obj_id = row.get("campaign_id") or row.get("id") or ""
            obj_name = row.get("campaign_name") or row.get("name") or ""
            cost = float(row.get("cost", 0) or row.get("spend", 0) or 0)
            revenue = float(row.get("revenue", 0) or 0)
            purchases = int(row.get("conversions", 0) or row.get("purchase", 0) or 0)
            clicks = int(row.get("clicks", 0) or 0)
            impressions = int(row.get("impressions", 0) or 0)
            # Detect traffic channel from sub tokens or name patterns
            channel = row.get("traffic_channel", "facebook")
            # Platform-native ID (sub2 often holds the native campaign ID in RT)
            platform_id = row.get("sub2", "") or row.get("platform_id", "") or str(obj_id)

            profit = revenue - cost
            roi = ((revenue - cost) / cost * 100) if cost > 0 else 0
            roas = (revenue / cost * 100) if cost > 0 else 0
            cpa = (cost / purchases) if purchases > 0 else 0
            cpc = (cost / clicks) if clicks > 0 else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cr = (purchases / clicks * 100) if clicks > 0 else 0
            epc = (revenue / clicks) if clicks > 0 else 0

            if obj_id and obj_name:
                results.append(CampaignData(
                    object_id=str(obj_id), object_name=str(obj_name),
                    traffic_channel=channel, object_type="campaign",
                    member_id=member_id, platform_id=str(platform_id),
                    cost=cost, revenue=revenue, profit=round(profit, 2),
                    purchase=purchases, clicks=clicks, impressions=impressions,
                    roi=round(roi, 2), roas=round(roas, 2),
                    cpa=round(cpa, 2), cpc=round(cpc, 2),
                    ctr=round(ctr, 2), cr=round(cr, 2), epc=round(epc, 2),
                ))

        return results


# ─── Mock Data ───────────────────────────────────────────────────

def _calc(cost, rev, clicks, imps, purch):
    roi = ((rev - cost) / cost * 100) if cost > 0 else 0
    roas = (rev / cost * 100) if cost > 0 else 0
    cpa = (cost / purch) if purch > 0 else 0
    cpc = (cost / clicks) if clicks > 0 else 0
    ctr = (clicks / imps * 100) if imps > 0 else 0
    cr = (purch / clicks * 100) if clicks > 0 else 0
    epc = (rev / clicks) if clicks > 0 else 0
    return roi, roas, cpa, cpc, ctr, cr, epc


def get_mock_campaigns(members: list = None) -> List[CampaignData]:
    """Generate realistic mock data. If members provided, assigns to them."""
    raw = [
        # member_idx, channel, obj_id, name, cost, rev, clicks, imps, purch, ic, atc, platform_id
        (0, "facebook", "rt_101", "[Renato] ED ALL-IN-ONE V3", 142.50, 387.00, 3420, 48200, 11, 3, 1, "23851234567890"),
        (0, "facebook", "rt_102", "[Renato] Brain Boost V2", 55.00, 12.00, 980, 15400, 0, 0, 0, "23851234567891"),
        (0, "facebook", "rt_103", "[Renato] ED Conta 6 BM MS", 195.00, 110.00, 4200, 61000, 4, 1, 0, "23851234567892"),
        (1, "facebook", "rt_201", "[Pedro] Geral - PAUSA ED", 89.30, 45.00, 1870, 31500, 2, 0, 0, "23851234567893"),
        (1, "facebook", "rt_202", "[Pedro] NV ErosLift Test", 320.00, 890.00, 8700, 125000, 32, 8, 4, "23851234567894"),
        (1, "facebook", "rt_203", "[Pedro] ALL-IN-ONE BW-04", 45.00, 0.00, 620, 9800, 0, 0, 0, "23851234567895"),
        (2, "facebook", "rt_301", "[Vini] ED Cartpanda Legacy", 210.00, 620.00, 5100, 72000, 18, 5, 2, "23851234567896"),
        (2, "facebook", "rt_302", "[Vini] ED VitalPRO Scale", 78.00, 195.00, 2100, 38000, 7, 2, 1, "23851234567897"),
        (0, "google", "rt_401", "Google_US_ED_Search_Brand", 180.00, 540.00, 2200, 18000, 15, 4, 2, "customers/123/campaigns/456"),
        (0, "google", "rt_402", "Google_US_Brain_Display", 95.00, 30.00, 4500, 120000, 1, 0, 0, "customers/123/campaigns/457"),
        (1, "google", "rt_403", "Google_BR_Recovery_PMAX", 260.00, 710.00, 6800, 95000, 22, 6, 3, "customers/123/campaigns/458"),
        (2, "google", "rt_404", "Google_US_ED_Shopping", 42.00, 0.00, 380, 5200, 0, 0, 0, "customers/123/campaigns/459"),
    ]

    results = []
    for midx, ch, oid, name, cost, rev, clicks, imps, purch, ic, atc, pid in raw:
        roi, roas, cpa, cpc, ctr, cr, epc = _calc(cost, rev, clicks, imps, purch)
        member_id = 0
        if members and midx < len(members):
            member_id = members[midx].id

        results.append(CampaignData(
            object_id=oid, object_name=name,
            traffic_channel=ch, object_type="campaign",
            member_id=member_id, platform_id=pid,
            cost=cost, revenue=rev, profit=round(rev - cost, 2),
            purchase=purch, clicks=clicks, impressions=imps,
            roi=round(roi, 2), roas=round(roas, 2),
            cpa=round(cpa, 2), cpc=round(cpc, 2),
            ctr=round(ctr, 2), cr=round(cr, 2), epc=round(epc, 2),
            initiate_checkout=ic, add_to_cart=atc,
            frequency=round(imps / max(clicks, 1) * 0.3, 1),
        ))

    return results
