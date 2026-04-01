import json
from typing import List

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, get_setting, set_setting
from models import (
    MonitorDecision, TRAFFIC_CHANNELS, METRICS, OPERATORS,
    ACTIONS, TIME_RANGES, SCHEDULE_FREQUENCIES,
)
from services.members import list_members, get_member, create_member, update_member, delete_member
from services.redtrack import RedTrackClient, get_mock_campaigns
from services.rules import (
    list_rules, create_rule, update_rule, delete_rule, get_rule,
    find_matching_action, save_log, list_logs,
    clear_monitor_results, save_monitor_result, list_monitor_results,
)
from services.platforms import execute_action
from services.notify import notify_rule_triggered
from services.scheduler import scheduler

app = FastAPI(title="RedTrack Rules Engine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()


# ─── Helpers ─────────────────────────────────────────────────────

def get_dry_run() -> bool:
    return get_setting("dry_run", "true").lower() == "true"


def _base_ctx(request, page):
    return {
        "request": request, "page": page,
        "dry_run": get_dry_run(),
        "redtrack_api_key": get_setting("redtrack_api_key", ""),
        "scheduler_status": scheduler.status,
        "members": list_members(),
        "traffic_channels": TRAFFIC_CHANNELS,
    }


def fetch_all_data():
    """Fetch data from RedTrack using global API key, or fallback to mock."""
    members = list_members()
    rt_key = get_setting("redtrack_api_key", "")
    all_data = []
    source = "mock"

    if rt_key and rt_key != "COLE_SUA_API_KEY_AQUI":
        try:
            client = RedTrackClient(api_key=rt_key)
            all_data = client.fetch_report()
            source = "api"
            save_log("INFO", "fetch_data", f"RedTrack API: {len(all_data)} objects loaded")
        except Exception as e:
            save_log("WARNING", "fetch_fallback", f"RedTrack API error: {e}")

    if not all_data:
        all_data = get_mock_campaigns(members)
        source = "mock"
        save_log("INFO", "fetch_mock", f"Using mock data ({len(all_data)} objects)")

    return all_data, source, members


def run_monitoring():
    dry_run = get_dry_run()
    rules = list_rules()
    all_data, source, members = fetch_all_data()
    members_map = {m.id: m for m in members}

    clear_monitor_results()
    decisions: List[MonitorDecision] = []

    for obj in all_data:
        match = find_matching_action(obj, rules)
        member = members_map.get(obj.member_id)
        member_name = member.name if member else "Unknown"

        if match:
            rule, action = match
            action_label = action.describe_action()

            if action.action == "notification":
                status = "NOTIFIED"
            elif dry_run:
                status = "DRY_RUN"
                save_log("WARNING", "dry_run",
                         f"Would {action_label} but DRY_RUN is ON",
                         object_id=obj.object_id, object_name=obj.object_name,
                         object_type=obj.object_type, traffic_channel=obj.traffic_channel,
                         member_name=member_name, cost=obj.cost, rule_name=rule.name)
            else:
                try:
                    if member and action.action != "notification":
                        execute_action(
                            member=member,
                            traffic_channel=obj.traffic_channel,
                            object_type=obj.object_type,
                            platform_id=obj.platform_id,
                            action=action.action,
                            scale_value=action.scale_value,
                        )
                    status = {
                        "pause": "PAUSED", "pause_restart": "PAUSED",
                        "scale_budget_up": "SCALED_UP", "scale_budget_down": "SCALED_DOWN",
                    }.get(action.action, "ACTED")

                    save_log("INFO", action.action, f"Executed: {action_label}",
                             object_id=obj.object_id, object_name=obj.object_name,
                             object_type=obj.object_type, traffic_channel=obj.traffic_channel,
                             member_name=member_name, cost=obj.cost, rule_name=rule.name)
                except Exception as e:
                    status = "ERROR"
                    save_log("ERROR", "execute_error", f"Error: {e}",
                             object_id=obj.object_id, object_name=obj.object_name,
                             object_type=obj.object_type, traffic_channel=obj.traffic_channel,
                             member_name=member_name, cost=obj.cost, rule_name=rule.name)

            # Notify
            if rule.notify_email or rule.notify_webhook:
                try:
                    notify_rule_triggered(
                        rule.name, action_label, obj.object_name, obj.object_id,
                        obj.traffic_channel, member_name,
                        {"cost": obj.cost, "revenue": obj.revenue, "roi": obj.roi},
                        rule.notify_email, rule.notify_webhook)
                except Exception:
                    pass

            matched_rule = rule.name
            matched_action = action_label
        else:
            status = "OK"
            matched_rule = None
            matched_action = None

        d = MonitorDecision(
            object_id=obj.object_id, object_name=obj.object_name,
            object_type=obj.object_type, traffic_channel=obj.traffic_channel,
            member_name=member_name, platform_id=obj.platform_id,
            cost=obj.cost, revenue=obj.revenue, roi=obj.roi,
            matched_rule=matched_rule, matched_action=matched_action, pause_status=status)
        save_monitor_result(d)
        decisions.append(d)

    return decisions, {
        "total": len(decisions),
        "matched": len([d for d in decisions if d.matched_rule]),
        "acted": len([d for d in decisions if d.pause_status not in ("OK",)]),
        "source": source, "dry_run": dry_run,
    }


# ═══════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════

# ─── Dashboard ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    results = list_monitor_results(200)
    logs = list_logs(20)
    ctx = _base_ctx(request, "dashboard")
    ctx.update({
        "rules_count": len(list_rules()),
        "total_objects": len(results),
        "matched_count": len([r for r in results if r["matched_rule"]]),
        "acted_count": len([r for r in results if r["pause_status"] not in ("OK",)]),
        "results": results,
        "logs": logs,
    })
    return templates.TemplateResponse("index.html", ctx)


# ─── Team ────────────────────────────────────────────────────────

@app.get("/team", response_class=HTMLResponse)
def team_page(request: Request):
    ctx = _base_ctx(request, "team")
    ctx["editing_member"] = None
    return templates.TemplateResponse("team.html", ctx)


@app.get("/team/{member_id}/edit", response_class=HTMLResponse)
def team_edit_page(request: Request, member_id: int):
    ctx = _base_ctx(request, "team")
    ctx["editing_member"] = get_member(member_id)
    return templates.TemplateResponse("team.html", ctx)


@app.post("/api/team/save")
async def api_team_save(request: Request):
    body = await request.json()
    mid = body.get("id")
    name = body["name"]
    email = body.get("email", "")
    tokens = {k: body.get(k, "") for k in [
        "fb_access_token", "fb_ad_account_id",
        "google_developer_token", "google_client_id", "google_client_secret",
        "google_refresh_token", "google_customer_id"
    ]}

    if mid:
        update_member(mid, name, email, **tokens)
        save_log("INFO", "update_member", f"Member updated: {name}", member_name=name)
    else:
        mid = create_member(name, email, **tokens)
        save_log("INFO", "create_member", f"Member created: {name}", member_name=name)

    return JSONResponse({"ok": True, "member_id": mid})


@app.post("/team/{member_id}/delete")
def team_delete(member_id: int):
    m = get_member(member_id)
    delete_member(member_id)
    save_log("WARNING", "delete_member", f"Member removed: {m.name if m else '?'}")
    return RedirectResponse(url="/team", status_code=303)


# ─── Rules ───────────────────────────────────────────────────────

@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    ctx = _base_ctx(request, "rules")
    ctx.update({
        "rules": list_rules(), "editing_rule": None, "editing_rule_json": "null",
        "metrics": METRICS, "operators": OPERATORS, "actions": ACTIONS,
        "time_ranges": TIME_RANGES, "schedule_frequencies": SCHEDULE_FREQUENCIES,
    })
    return templates.TemplateResponse("rules.html", ctx)


@app.get("/rules/{rule_id}/edit", response_class=HTMLResponse)
def edit_rule_page(request: Request, rule_id: int):
    editing = get_rule(rule_id)
    ctx = _base_ctx(request, "rules")
    ctx.update({
        "rules": list_rules(), "editing_rule": editing,
        "editing_rule_json": json.dumps({
            "id": editing.id, "name": editing.name,
            "member_id": editing.member_id,
            "traffic_channel": editing.traffic_channel,
            "rule_object": editing.rule_object,
            "campaign_filter": editing.campaign_filter,
            "schedule_minutes": editing.schedule_minutes,
            "notify_email": editing.notify_email,
            "notify_webhook": editing.notify_webhook,
            "active": editing.active,
            "actions": [{
                "action": a.action, "scale_value": a.scale_value,
                "conditions": [{"metric": c.metric, "operator": c.operator,
                                "value": c.value, "time_range": c.time_range}
                               for c in a.conditions]
            } for a in editing.actions]
        }) if editing else "null",
        "metrics": METRICS, "operators": OPERATORS, "actions": ACTIONS,
        "time_ranges": TIME_RANGES, "schedule_frequencies": SCHEDULE_FREQUENCIES,
    })
    return templates.TemplateResponse("rules.html", ctx)


@app.post("/api/rules/save")
async def api_save_rule(request: Request):
    body = await request.json()
    kwargs = {
        "name": body["name"],
        "member_id": int(body["member_id"]),
        "traffic_channel": body["traffic_channel"],
        "rule_object": body["rule_object"],
        "campaign_filter": body.get("campaign_filter", ""),
        "actions_data": body.get("actions", []),
        "schedule_minutes": int(body.get("schedule_minutes", 5)),
        "notify_email": body.get("notify_email", ""),
        "notify_webhook": body.get("notify_webhook", ""),
        "active": bool(body.get("active", True)),
    }
    rid = body.get("id")
    if rid:
        update_rule(rid, **kwargs)
        return JSONResponse({"ok": True, "rule_id": rid})
    else:
        new_id = create_rule(**kwargs)
        return JSONResponse({"ok": True, "rule_id": new_id})


@app.post("/rules/{rule_id}/delete")
def rules_delete(rule_id: int):
    rule = get_rule(rule_id)
    delete_rule(rule_id)
    save_log("WARNING", "delete_rule", "Rule removed", rule_name=rule.name if rule else None)
    return RedirectResponse(url="/rules", status_code=303)


# ─── Logs ────────────────────────────────────────────────────────

@app.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    ctx = _base_ctx(request, "logs")
    ctx["logs"] = list_logs(200)
    return templates.TemplateResponse("logs.html", ctx)


# ─── Monitoring ──────────────────────────────────────────────────

@app.post("/monitor/run")
def monitor_run():
    decisions, summary = run_monitoring()
    return JSONResponse({"ok": True, "summary": summary,
                         "results": [d.__dict__ for d in decisions]})


# ─── Manual pause ────────────────────────────────────────────────

@app.post("/api/objects/{object_id}/pause")
async def pause_manual(object_id: str, request: Request):
    body = await request.json()
    dry_run = get_dry_run()
    member = get_member(int(body.get("member_id", 0))) if body.get("member_id") else None

    try:
        if dry_run:
            save_log("WARNING", "manual_pause", "DRY_RUN — simulated",
                     object_id=object_id, object_name=body.get("object_name"),
                     member_name=member.name if member else None)
            return JSONResponse({"ok": True, "status": "DRY_RUN"})

        if member:
            execute_action(member, body.get("traffic_channel", "facebook"),
                           body.get("object_type", "campaign"),
                           body.get("platform_id", object_id), "pause")
        save_log("INFO", "manual_pause", "Paused manually",
                 object_id=object_id, object_name=body.get("object_name"),
                 member_name=member.name if member else None)
        return JSONResponse({"ok": True, "status": "PAUSED"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ─── Settings ────────────────────────────────────────────────────

@app.post("/settings/dry-run")
def toggle_dry_run(enabled: str = Form(...)):
    set_setting("dry_run", "true" if enabled == "true" else "false")
    save_log("INFO", "toggle_dry_run", f"DRY_RUN → {enabled}")
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/settings/redtrack-key")
async def save_redtrack_key(request: Request):
    body = await request.json()
    key = body.get("api_key", "").strip()
    set_setting("redtrack_api_key", key)
    save_log("INFO", "update_redtrack_key", "RedTrack API key updated")
    return JSONResponse({"ok": True})


# ─── Scheduler ───────────────────────────────────────────────────

@app.post("/api/scheduler/start")
async def sched_start(request: Request):
    body = await request.json()
    interval = int(body.get("interval_minutes", 5))
    scheduler.start(callback=run_monitoring, interval_minutes=interval)
    save_log("INFO", "scheduler_start", f"Started (every {interval}min)")
    return JSONResponse({"ok": True, "status": scheduler.status})


@app.post("/api/scheduler/stop")
def sched_stop():
    scheduler.stop()
    save_log("INFO", "scheduler_stop", "Stopped")
    return JSONResponse({"ok": True, "status": scheduler.status})


@app.get("/api/scheduler/status")
def sched_status():
    return JSONResponse(scheduler.status)


@app.get("/api/channels")
def api_channels():
    return JSONResponse(TRAFFIC_CHANNELS)
