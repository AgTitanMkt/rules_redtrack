from typing import List, Optional, Tuple
from database import db_cursor
from models import Rule, RuleAction, Condition, CampaignData, MonitorDecision


def _build_rule(row, cur) -> Rule:
    rid = row["id"]
    # Get linked ad accounts
    cur.execute("""SELECT a.id, a.name FROM rule_ad_accounts ra
        JOIN ad_accounts a ON a.id = ra.ad_account_id WHERE ra.rule_id=?""", (rid,))
    accs = cur.fetchall()
    acc_ids = [a["id"] for a in accs]
    acc_names = [a["name"] for a in accs]

    # Get actions + conditions
    cur.execute("SELECT * FROM rule_actions WHERE rule_id=? ORDER BY sort_order", (rid,))
    actions = []
    for ar in cur.fetchall():
        cur.execute("SELECT * FROM action_conditions WHERE action_id=? ORDER BY id", (ar["id"],))
        conds = [Condition(metric=c["metric"], operator=c["operator"],
                           value=float(c["value"]), time_range=c["time_range"])
                 for c in cur.fetchall()]
        actions.append(RuleAction(action=ar["action"], conditions=conds,
                                  scale_value=float(ar["scale_value"]) if ar["scale_value"] else None))

    return Rule(id=rid, name=row["name"], ad_account_ids=acc_ids, ad_account_names=acc_names,
                rule_object=row["rule_object"], campaign_filter=row["campaign_filter"],
                actions=actions, schedule_minutes=int(row["schedule_minutes"]),
                notify_email=row["notify_email"] or "", notify_webhook=row["notify_webhook"] or "",
                active=bool(row["active"]), created_at=row["created_at"])


def list_rules() -> List[Rule]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM rules ORDER BY id DESC")
        return [_build_rule(r, cur) for r in cur.fetchall()]


def get_rule(rule_id: int) -> Optional[Rule]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM rules WHERE id=?", (rule_id,))
        row = cur.fetchone()
        return _build_rule(row, cur) if row else None


def create_rule(name, ad_account_ids, rule_object, campaign_filter,
                actions_data, schedule_minutes=5, notify_email="", notify_webhook="", active=True) -> int:
    with db_cursor(commit=True) as cur:
        cur.execute("""INSERT INTO rules (name,rule_object,campaign_filter,schedule_minutes,
            notify_email,notify_webhook,active) VALUES (?,?,?,?,?,?,?)""",
            (name, rule_object, campaign_filter, schedule_minutes, notify_email, notify_webhook, int(active)))
        rid = cur.lastrowid
        for aid in ad_account_ids:
            cur.execute("INSERT INTO rule_ad_accounts (rule_id,ad_account_id) VALUES (?,?)", (rid, aid))
        _save_actions(cur, rid, actions_data)
        return rid


def update_rule(rule_id, name, ad_account_ids, rule_object, campaign_filter,
                actions_data, schedule_minutes=5, notify_email="", notify_webhook="", active=True):
    with db_cursor(commit=True) as cur:
        cur.execute("""UPDATE rules SET name=?,rule_object=?,campaign_filter=?,schedule_minutes=?,
            notify_email=?,notify_webhook=?,active=? WHERE id=?""",
            (name, rule_object, campaign_filter, schedule_minutes, notify_email, notify_webhook, int(active), rule_id))
        cur.execute("DELETE FROM rule_ad_accounts WHERE rule_id=?", (rule_id,))
        for aid in ad_account_ids:
            cur.execute("INSERT INTO rule_ad_accounts (rule_id,ad_account_id) VALUES (?,?)", (rule_id, aid))
        cur.execute("DELETE FROM rule_actions WHERE rule_id=?", (rule_id,))
        _save_actions(cur, rule_id, actions_data)


def _save_actions(cur, rule_id, actions_data):
    for idx, ad in enumerate(actions_data):
        cur.execute("INSERT INTO rule_actions (rule_id,action,scale_value,sort_order) VALUES (?,?,?,?)",
                    (rule_id, ad["action"], ad.get("scale_value"), idx))
        aid = cur.lastrowid
        for c in ad.get("conditions", []):
            cur.execute("INSERT INTO action_conditions (action_id,metric,operator,value,time_range) VALUES (?,?,?,?,?)",
                        (aid, c["metric"], c["operator"], float(c["value"]), c.get("time_range", "today")))


def delete_rule(rule_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM rules WHERE id=?", (rule_id,))


# ─── Evaluation ──────────────────────────────────────────────────

def evaluate_condition(cond: Condition, data: CampaignData) -> bool:
    actual = data.get_metric(cond.metric)
    t = cond.value
    op = cond.operator
    if op == "gt":  return actual > t
    if op == "gte": return actual >= t
    if op == "lt":  return actual < t
    if op == "lte": return actual <= t
    if op == "eq":  return actual == t
    return False


def find_matching_action(data: CampaignData, rules: List[Rule]) -> Optional[Tuple[Rule, RuleAction]]:
    for rule in rules:
        if not rule.active:
            continue
        if data.ad_account_id not in rule.ad_account_ids:
            continue
        if rule.campaign_filter and rule.campaign_filter.lower() not in data.object_name.lower():
            continue
        for action in rule.actions:
            if not action.conditions:
                continue
            if all(evaluate_condition(c, data) for c in action.conditions):
                return (rule, action)
    return None


# ─── Logs ────────────────────────────────────────────────────────

def save_log(level, action, message, **kw):
    with db_cursor(commit=True) as cur:
        cur.execute("""INSERT INTO logs (level,action,object_id,object_name,ad_account_name,
            platform,owner,cost,rule_name,message) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (level, action, kw.get("object_id"), kw.get("object_name"),
             kw.get("ad_account_name"), kw.get("platform"), kw.get("owner"),
             kw.get("cost"), kw.get("rule_name"), message))


def list_logs(limit=100):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()


def clear_monitor_results():
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM monitor_results")


def save_monitor_result(d: MonitorDecision):
    with db_cursor(commit=True) as cur:
        cur.execute("""INSERT INTO monitor_results (object_id,object_name,object_type,
            ad_account_name,platform,owner,platform_id,cost,revenue,roi,
            matched_rule,matched_action,pause_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.object_id, d.object_name, d.object_type, d.ad_account_name,
             d.platform, d.owner, d.platform_id, d.cost, d.revenue, d.roi,
             d.matched_rule, d.matched_action, d.pause_status))


def list_monitor_results(limit=200):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM monitor_results ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()
