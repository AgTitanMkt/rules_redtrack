import os
import requests
from typing import List
from models import CampaignData

REDTRACK_BASE_URL = os.getenv("REDTRACK_BASE_URL", "https://api.redtrack.io")


class RedTrackClient:
    def __init__(self, api_key=""):
        self.base_url = REDTRACK_BASE_URL.rstrip("/")
        self.api_key = api_key

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json", "Content-Type": "application/json"}

    def fetch_report(self) -> List[CampaignData]:
        if not self.api_key:
            raise RuntimeError("No RedTrack API key")
        url = f"{self.base_url}/report"
        payload = {"group_by": ["campaign"], "metrics": ["cost","revenue","profit","conversions","clicks","impressions"], "limit": 500}
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("rows", data) if isinstance(data, dict) else data
        results = []
        for row in rows:
            oid = row.get("campaign_id") or row.get("id") or ""
            name = row.get("campaign_name") or row.get("name") or ""
            cost = float(row.get("cost",0) or row.get("spend",0) or 0)
            rev = float(row.get("revenue",0) or 0)
            purch = int(row.get("conversions",0) or 0)
            clicks = int(row.get("clicks",0) or 0)
            imps = int(row.get("impressions",0) or 0)
            ch = row.get("traffic_channel","facebook")
            pid = row.get("sub2","") or str(oid)
            profit = rev - cost
            roi = ((rev-cost)/cost*100) if cost>0 else 0
            roas = (rev/cost*100) if cost>0 else 0
            cpa = (cost/purch) if purch>0 else 0
            cpc = (cost/clicks) if clicks>0 else 0
            ctr = (clicks/imps*100) if imps>0 else 0
            cr = (purch/clicks*100) if clicks>0 else 0
            epc = (rev/clicks) if clicks>0 else 0
            if oid and name:
                results.append(CampaignData(
                    object_id=str(oid), object_name=name, ad_account_id=0,
                    ad_account_name="", platform=ch, object_type="campaign",
                    platform_id=pid, cost=cost, revenue=rev, profit=round(profit,2),
                    purchase=purch, clicks=clicks, impressions=imps,
                    roi=round(roi,2), roas=round(roas,2), cpa=round(cpa,2),
                    cpc=round(cpc,2), ctr=round(ctr,2), cr=round(cr,2), epc=round(epc,2)))
        return results


def _c(cost, rev, clicks, imps, purch):
    roi = ((rev-cost)/cost*100) if cost>0 else 0
    roas = (rev/cost*100) if cost>0 else 0
    cpa = (cost/purch) if purch>0 else 0
    cpc = (cost/clicks) if clicks>0 else 0
    ctr = (clicks/imps*100) if imps>0 else 0
    cr = (purch/clicks*100) if clicks>0 else 0
    epc = (rev/clicks) if clicks>0 else 0
    return roi, roas, cpa, cpc, ctr, cr, epc


def get_mock_campaigns(accounts: list = None) -> List[CampaignData]:
    """Mock data: each ad account has campaigns under it, like RT Traffic Channels."""
    if not accounts:
        return []

    acc_map = {a.name: a for a in accounts}
    raw = [
        # (account_name, campaign, cost, rev, clicks, imps, purch, ic, atc, pid)
        ("ED [FBR-RENATO]", "ED_US_Brain_V1", 142.50, 387.00, 3420, 48200, 11, 3, 1, "23851001"),
        ("ED [FBR-RENATO]", "ED_US_AllInOne_V3", 195.00, 110.00, 4200, 61000, 4, 1, 0, "23851002"),
        ("ED [FBR-RENATO]", "ED_US_BrainBoost_V2", 55.00, 12.00, 980, 15400, 0, 0, 0, "23851003"),
        ("ED [FBR-RENATO] - BIDCAP", "ED_BIDCAP_Scale01", 89.30, 245.00, 2100, 31500, 7, 2, 1, "23851010"),
        ("ED [FBR-RENATO] - BIDCAP", "ED_BIDCAP_Test02", 45.00, 0.00, 620, 9800, 0, 0, 0, "23851011"),
        ("ED [FBR-PEDRO]", "ED_Pedro_Geral_V1", 89.30, 45.00, 1870, 31500, 2, 0, 0, "23851020"),
        ("ED [FBR-PEDRO]", "ED_Pedro_ErosLift", 320.00, 890.00, 8700, 125000, 32, 8, 4, "23851021"),
        ("ED [FBR-PEDRO]", "ED_Pedro_AllInOne_BW04", 45.00, 0.00, 620, 9800, 0, 0, 0, "23851022"),
        ("ED [FBR-VINI]", "ED_Vini_Cartpanda", 210.00, 620.00, 5100, 72000, 18, 5, 2, "23851030"),
        ("ED [FBR-VINI]", "ED_Vini_VitalPRO", 78.00, 195.00, 2100, 38000, 7, 2, 1, "23851031"),
        ("ED [FBR-VINI]", "ED_Vini_NI10", 81.87, 0.00, 1200, 18000, 0, 0, 0, "23851032"),
        ("GAADS - DIME - CONTA CESIO", "Google_ED_Search_Brand", 180.00, 540.00, 2200, 18000, 15, 4, 2, "cust/123/camp/456"),
        ("GAADS - DIME - CONTA CESIO", "Google_ED_Display", 95.00, 30.00, 4500, 120000, 1, 0, 0, "cust/123/camp/457"),
        ("GAADS - DIME - CONTA CESIO", "Google_ED_Shopping", 42.00, 0.00, 380, 5200, 0, 0, 0, "cust/123/camp/459"),
    ]

    results = []
    for acc_name, camp, cost, rev, clicks, imps, purch, ic, atc, pid in raw:
        acc = acc_map.get(acc_name)
        if not acc:
            continue
        roi, roas, cpa, cpc, ctr, cr, epc = _c(cost, rev, clicks, imps, purch)
        results.append(CampaignData(
            object_id=f"rt_{len(results)+100}", object_name=camp,
            ad_account_id=acc.id, ad_account_name=acc.name,
            platform=acc.platform, object_type="campaign", platform_id=pid,
            cost=cost, revenue=rev, profit=round(rev-cost,2),
            purchase=purch, clicks=clicks, impressions=imps,
            roi=round(roi,2), roas=round(roas,2), cpa=round(cpa,2),
            cpc=round(cpc,2), ctr=round(ctr,2), cr=round(cr,2), epc=round(epc,2),
            initiate_checkout=ic, add_to_cart=atc))
    return results
