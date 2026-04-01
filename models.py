from dataclasses import dataclass, field
from typing import Optional, List

# ─── Platform Types ──────────────────────────────────────────────

PLATFORM_TYPES = {
    "facebook": {"label": "Facebook / Meta Ads", "icon": "fb"},
    "google": {"label": "Google Ads", "icon": "gg"},
    "taboola": {"label": "Taboola", "icon": "tb"},
    "outbrain": {"label": "Outbrain", "icon": "ob"},
    "newsbreak": {"label": "Newsbreak", "icon": "nb"},
    "mgid": {"label": "MGID", "icon": "mg"},
    "tiktok": {"label": "TikTok Ads", "icon": "tt"},
    "other": {"label": "Other", "icon": "ot"},
}

RULE_OBJECTS = [
    {"value": "channel_campaign", "label": "Channel Campaign (Traffic Channel)"},
    {"value": "campaign", "label": "Campaign"},
    {"value": "adset", "label": "Ad Set / Ad Group"},
    {"value": "ad", "label": "Ad / Creative"},
]

METRICS = [
    {"value": "cost", "label": "Cost (Spend)", "type": "currency"},
    {"value": "revenue", "label": "Revenue", "type": "currency"},
    {"value": "profit", "label": "Profit", "type": "currency"},
    {"value": "purchase", "label": "Purchases", "type": "number"},
    {"value": "clicks", "label": "Clicks", "type": "number"},
    {"value": "impressions", "label": "Impressions", "type": "number"},
    {"value": "roi", "label": "ROI %", "type": "percent"},
    {"value": "roas", "label": "ROAS %", "type": "percent"},
    {"value": "cpa", "label": "CPA", "type": "currency"},
    {"value": "cpc", "label": "CPC", "type": "currency"},
    {"value": "ctr", "label": "CTR %", "type": "percent"},
    {"value": "cr", "label": "CR %", "type": "percent"},
    {"value": "epc", "label": "EPC", "type": "currency"},
    {"value": "initiate_checkout", "label": "InitiateCheckout", "type": "number"},
    {"value": "add_to_cart", "label": "AddToCart", "type": "number"},
    {"value": "frequency", "label": "Frequency", "type": "number"},
]

OPERATORS = [
    {"value": "gt", "label": "greater than", "symbol": ">"},
    {"value": "gte", "label": "greater or equal", "symbol": "≥"},
    {"value": "lt", "label": "less than", "symbol": "<"},
    {"value": "lte", "label": "less or equal", "symbol": "≤"},
    {"value": "eq", "label": "equal to", "symbol": "="},
]

ACTIONS = [
    {"value": "pause", "label": "Pause"},
    {"value": "pause_restart", "label": "Pause and Restart"},
    {"value": "notification", "label": "Notification Only"},
]

TIME_RANGES = [
    {"value": "today", "label": "Today"},
    {"value": "yesterday", "label": "Yesterday"},
    {"value": "last_3d", "label": "Last 3 days"},
    {"value": "last_7d", "label": "Last 7 days"},
    {"value": "last_14d", "label": "Last 14 days"},
    {"value": "last_30d", "label": "Last 30 days"},
    {"value": "lifetime", "label": "Lifetime"},
]

SCHEDULE_FREQUENCIES = [
    {"value": "5", "label": "Every 5 min"},
    {"value": "15", "label": "Every 15 min"},
    {"value": "30", "label": "Every 30 min"},
    {"value": "60", "label": "Every 1 hour"},
]


# ─── Data classes ────────────────────────────────────────────────

@dataclass
class AdAccount:
    """
    One Traffic Channel in RedTrack = one Ad Account here.
    e.g. "ED [FBR-RENATO]" is a Facebook account with Meta API connected.
    """
    id: int
    name: str                    # e.g. "ED [FBR-RENATO]" or "GAADS - DIME - CONTA CESIO"
    platform: str                # facebook, google, taboola, etc.
    owner: str                   # media buyer name: Renato, Pedro, Vini
    # RedTrack campaign ID (the # column in RT)
    rt_campaign_id: str = ""
    # Facebook credentials
    fb_access_token: str = ""
    fb_ad_account_id: str = ""   # act_xxxxx
    fb_pixel_id: str = ""
    # Google credentials
    google_ads_account_id: str = ""  # e.g. 820-096-1286
    google_mcc_id: str = ""
    google_developer_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    # Status
    active: bool = True
    created_at: str = ""

    @property
    def platform_label(self) -> str:
        return PLATFORM_TYPES.get(self.platform, {}).get("label", self.platform)

    def has_api(self) -> bool:
        if self.platform == "facebook":
            return bool(self.fb_access_token and self.fb_ad_account_id)
        elif self.platform == "google":
            return bool(self.google_ads_account_id and self.google_refresh_token)
        return False

    def mask(self, val: str) -> str:
        if not val or len(val) < 8:
            return "••••" if val else ""
        return val[:4] + "••••" + val[-4:]


@dataclass
class Condition:
    metric: str
    operator: str
    value: float
    time_range: str = "today"

    def describe(self) -> str:
        ml = next((m["label"] for m in METRICS if m["value"] == self.metric), self.metric)
        os_ = next((o["symbol"] for o in OPERATORS if o["value"] == self.operator), self.operator)
        tl = next((t["label"] for t in TIME_RANGES if t["value"] == self.time_range), self.time_range)
        return f"{ml} {os_} {self.value} ({tl})"


@dataclass
class RuleAction:
    action: str
    conditions: List[Condition] = field(default_factory=list)
    scale_value: Optional[float] = None

    def describe_action(self) -> str:
        return next((a["label"] for a in ACTIONS if a["value"] == self.action), self.action)


@dataclass
class Rule:
    id: int
    name: str
    ad_account_ids: List[int]    # which traffic channels this rule applies to
    ad_account_names: List[str]  # denormalized for display
    rule_object: str             # channel_campaign, campaign, adset, ad
    campaign_filter: str         # text match on campaign name
    actions: List[RuleAction] = field(default_factory=list)
    schedule_minutes: int = 5
    notify_email: str = ""
    notify_webhook: str = ""
    active: bool = True
    created_at: str = ""

    @property
    def object_label(self) -> str:
        return next((r["label"] for r in RULE_OBJECTS if r["value"] == self.rule_object), self.rule_object)

    @property
    def accounts_display(self) -> str:
        if len(self.ad_account_names) <= 2:
            return ", ".join(self.ad_account_names)
        return f"{self.ad_account_names[0]} +{len(self.ad_account_names)-1} more"


@dataclass
class CampaignData:
    object_id: str
    object_name: str
    ad_account_id: int           # FK to ad_accounts
    ad_account_name: str
    platform: str
    object_type: str
    platform_id: str = ""        # native platform ID for pause
    cost: float = 0.0
    revenue: float = 0.0
    profit: float = 0.0
    purchase: int = 0
    clicks: int = 0
    impressions: int = 0
    roi: float = 0.0
    roas: float = 0.0
    cpa: float = 0.0
    cpc: float = 0.0
    ctr: float = 0.0
    cr: float = 0.0
    epc: float = 0.0
    initiate_checkout: int = 0
    add_to_cart: int = 0
    frequency: float = 0.0

    def get_metric(self, metric_name: str) -> float:
        return float(getattr(self, metric_name, 0))


@dataclass
class MonitorDecision:
    object_id: str
    object_name: str
    object_type: str
    ad_account_name: str
    platform: str
    owner: str
    platform_id: str
    cost: float
    revenue: float
    roi: float
    matched_rule: Optional[str]
    matched_action: Optional[str]
    pause_status: str
