from dataclasses import dataclass, field
from typing import Optional, List


# ─── Traffic Channels & Platform Config ──────────────────────────

TRAFFIC_CHANNELS = {
    "facebook": {
        "label": "Facebook / Meta Ads",
        "icon": "fb",
        "rule_objects": [
            {"value": "campaign", "label": "Campaign"},
            {"value": "adset", "label": "Ad Set"},
            {"value": "ad", "label": "Ad / Creative"},
        ],
        "token_fields": [
            {"key": "fb_access_token", "label": "Access Token (Meta)", "placeholder": "EAAxxxxxx...", "type": "password"},
            {"key": "fb_ad_account_id", "label": "Ad Account ID", "placeholder": "act_123456789", "type": "text"},
        ],
    },
    "google": {
        "label": "Google Ads",
        "icon": "gg",
        "rule_objects": [
            {"value": "campaign", "label": "Campaign"},
            {"value": "adgroup", "label": "Ad Group"},
            {"value": "ad", "label": "Ad"},
        ],
        "token_fields": [
            {"key": "google_developer_token", "label": "Developer Token", "placeholder": "xxxx-xxxx-xxxx", "type": "password"},
            {"key": "google_client_id", "label": "OAuth Client ID", "placeholder": "123456.apps.googleusercontent.com", "type": "text"},
            {"key": "google_client_secret", "label": "OAuth Client Secret", "placeholder": "GOCSPx-...", "type": "password"},
            {"key": "google_refresh_token", "label": "Refresh Token", "placeholder": "1//0xxx...", "type": "password"},
            {"key": "google_customer_id", "label": "Customer ID (MCC or account)", "placeholder": "123-456-7890", "type": "text"},
        ],
    },
}

METRICS = [
    {"value": "cost", "label": "Cost (Spend)", "type": "currency"},
    {"value": "revenue", "label": "Revenue", "type": "currency"},
    {"value": "profit", "label": "Profit", "type": "currency"},
    {"value": "purchase", "label": "Purchases (Conversions)", "type": "number"},
    {"value": "clicks", "label": "Clicks", "type": "number"},
    {"value": "impressions", "label": "Impressions", "type": "number"},
    {"value": "roi", "label": "ROI %", "type": "percent"},
    {"value": "roas", "label": "ROAS %", "type": "percent"},
    {"value": "cpa", "label": "CPA (Cost per Acquisition)", "type": "currency"},
    {"value": "cpc", "label": "CPC (Cost per Click)", "type": "currency"},
    {"value": "ctr", "label": "CTR %", "type": "percent"},
    {"value": "cr", "label": "CR % (Conversion Rate)", "type": "percent"},
    {"value": "epc", "label": "EPC (Earnings per Click)", "type": "currency"},
    {"value": "initiate_checkout", "label": "Initiate Checkout", "type": "number"},
    {"value": "add_to_cart", "label": "Add to Cart", "type": "number"},
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
    {"value": "scale_budget_up", "label": "Scale Budget Up"},
    {"value": "scale_budget_down", "label": "Scale Budget Down"},
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
class TeamMember:
    id: int
    name: str
    email: str
    fb_access_token: str = ""
    fb_ad_account_id: str = ""
    google_developer_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_customer_id: str = ""
    created_at: str = ""

    def has_fb_token(self) -> bool:
        return bool(self.fb_access_token and self.fb_ad_account_id)

    def has_google_token(self) -> bool:
        return bool(self.google_developer_token and self.google_refresh_token and self.google_customer_id)

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
        label = next((a["label"] for a in ACTIONS if a["value"] == self.action), self.action)
        if self.scale_value and "scale" in self.action:
            return f"{label} {self.scale_value}%"
        return label


@dataclass
class Rule:
    id: int
    name: str
    member_id: int
    member_name: str
    traffic_channel: str
    rule_object: str
    campaign_filter: str
    actions: List[RuleAction] = field(default_factory=list)
    schedule_minutes: int = 5
    notify_email: str = ""
    notify_webhook: str = ""
    active: bool = True
    created_at: str = ""

    @property
    def channel_label(self) -> str:
        return TRAFFIC_CHANNELS.get(self.traffic_channel, {}).get("label", self.traffic_channel)

    @property
    def object_label(self) -> str:
        ch = TRAFFIC_CHANNELS.get(self.traffic_channel, {})
        for obj in ch.get("rule_objects", []):
            if obj["value"] == self.rule_object:
                return obj["label"]
        return self.rule_object


@dataclass
class CampaignData:
    object_id: str
    object_name: str
    traffic_channel: str
    object_type: str
    member_id: int = 0
    platform_id: str = ""   # native platform ID for pause/restart
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
    traffic_channel: str
    member_name: str
    platform_id: str
    cost: float
    revenue: float
    roi: float
    matched_rule: Optional[str]
    matched_action: Optional[str]
    pause_status: str
