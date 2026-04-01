from typing import List, Optional, Tuple
from database import db_cursor
from models import Rule, RuleAction, Condition, CampaignData, MonitorDecision


# ─── Rule CRUD ───────────────────────────────────────────────────

def _build_rule(row, cur) -> Rule:
    rule_id = row["id"]
    cur.execute("SELECT * FROM rule_actions WHERE rule_id = ? ORDER BY sort_order", (rule_id,))
    action_rows = cur.fetchall()
    actions = []
    for ar in action_rows:
        cur.execute("SELECT * FROM action_conditions WHERE action_id = ? ORDER BY id", (ar["id"],))
        cond_rows = cur.fetchall()
        conditions = [
            Condition(metric=c["metric"], operator=c["operator"],
                      value=float(c["value"]), time_range=c["time_range"])
            for c in cond_rows
        ]
        actions.append(RuleAction(
            action=ar["action"], conditions=conditions,
            scale_value=float(ar["scale_value"]) if ar["scale_value"] else None,
        ))

    # Get member name
    cur.execute("SELECT name FROM team_members WHERE id = ?", (row["member_id"],))
    mrow = cur.fetchone()
    member_name = mrow["name"] if mrow else "Unknown"

    return Rule(
        id=row["id"], name=row["name"],
        member_id=row["member_id"], member_name=member_name,
        traffic_channel=row["traffic_channel"], rule_object=row["rule_object"],
        campaign_filter=row["campaign_filter"], actions=actions,
        schedule_minutes=int(row["schedule_minutes"]),
        notify_email=row["notify_email"] or "",
        notify_webhook=row["notify_webhook"] or "",
        active=bool(row["active"]), created_at=row["created_at"],
    )


def list_rules(member_id: int = None) -> List[Rule]:
    with db_cursor() as cur:
        if member_id:
            cur.execute("SELECT * FROM rules WHERE member_id = ? ORDER BY id DESC", (member_id,))
        else:
            cur.execute("SELECT * FROM rules ORDER BY id DESC")
        return [_build_rule(r, cur) for r in cur.fetchall()]


def get_rule(rule_id: int) -> Optional[Rule]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
        row = cur.fetchone()
        return _build_rule(row, cur) if row else None


def create_rule(name, member_id, traffic_channel, rule_object, campaign_filter,
                actions_data, schedule_minutes=5, notify_email="", notify_webhook="", active=True) -> int:
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO rules (name, member_id, traffic_channel, rule_object, campaign_filter,
                               schedule_minutes, notify_email, notify_webhook, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, member_id, traffic_channel, rule_object, campaign_filter,
              schedule_minutes, notify_email, notify_webhook, int(active)))
        rule_id = cur.lastrowid
        _save_actions(cur, rule_id, actions_data)
        return rule_id


def update_rule(rule_id, name, member_id, traffic_channel, rule_object, campaign_filter,
                actions_data, schedule_minutes=5, notify_email="", notify_webhook="", active=True):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE rules SET name=?, member_id=?, traffic_channel=?, rule_object=?, campaign_filter=?,
                schedule_minutes=?, notify_email=?, notify_webhook=?, active=?
            WHERE id=?
        """, (name, member_id, traffic_channel, rule_object, campaign_filter,
              schedule_minutes, notify_email, notify_webhook, int(active), rule_id))
        cur.execute("DELETE FROM rule_actions WHERE rule_id = ?", (rule_id,))
        _save_actions(cur, rule_id, actions_data)


def _save_actions(cur, rule_id, actions_data):
    for idx, ad in enumerate(actions_data):
        cur.execute("""
            INSERT INTO rule_actions (rule_id, action, scale_value, sort_order)
            VALUES (?, ?, ?, ?)
        """, (rule_id, ad["action"], ad.get("scale_value"), idx))
        action_id = cur.lastrowid
        for cond in ad.get("conditions", []):
            cur.execute("""
                INSERT INTO action_conditions (action_id, metric, operator, value, time_range)
                VALUES (?, ?, ?, ?, ?)
            """, (action_id, cond["metric"], cond["operator"],
                  float(cond["value"]), cond.get("time_range", "today")))


def delete_rule(rule_id: int):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM rules WHERE id = ?", (rule_id,))


# ─── Condition Evaluation ────────────────────────────────────────

def evaluate_condition(cond: Condition, data: CampaignData) -> bool:
    actual = data.get_metric(cond.metric)
    target = cond.value
    op = cond.operator
    if op == "gt":  return actual > target
    if op == "gte": return actual >= target
    if op == "lt":  return actual < target
    if op == "lte": return actual <= target
    if op == "eq":  return actual == target
    return False


def find_matching_action(data: CampaignData, rules: List[Rule]) -> Optional[Tuple[Rule, RuleAction]]:
    """
    For a given campaign data object, find first matching rule+action.
    Matches on: member_id, traffic_channel, rule_object, campaign_filter, all conditions.
    """
    for rule in rules:
        if not rule.active:
            continue
        # Rule must belong to the same member
        if rule.member_id != data.member_id:
            continue
        if rule.traffic_channel != data.traffic_channel:
            continue
        if rule.rule_object != data.object_type:
            continue
        if rule.campaign_filter:
            if rule.campaign_filter.lower() not in data.object_name.lower():
                continue

        for action in rule.actions:
            if not action.conditions:
                continue
            if all(evaluate_condition(c, data) for c in action.conditions):
                return (rule, action)

    return None


# ─── Logs ────────────────────────────────────────────────────────

def save_log(level, action, message, object_id=None, object_name=None,
             object_type=None, traffic_channel=None, member_name=None, cost=None, rule_name=None):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO logs (level, action, object_id, object_name, object_type,
                              traffic_channel, member_name, cost, rule_name, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (level, action, object_id, object_name, object_type,
              traffic_channel, member_name, cost, rule_name, message))


def list_logs(limit=100):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()


# ─── Monitor Results ─────────────────────────────────────────────

def clear_monitor_results():
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM monitor_results")


def save_monitor_result(d: MonitorDecision):
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO monitor_results
                (object_id, object_name, object_type, traffic_channel,
                 member_name, platform_id, cost, revenue, roi,
                 matched_rule, matched_action, pause_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d.object_id, d.object_name, d.object_type, d.traffic_channel,
              d.member_name, d.platform_id, d.cost, d.revenue, d.roi,
              d.matched_rule, d.matched_action, d.pause_status))


def list_monitor_results(limit=200):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM monitor_results ORDER BY id DESC LIMIT ?", (limit,))
        return cur.fetchall()
