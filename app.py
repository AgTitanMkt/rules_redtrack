import json
from typing import List
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, get_setting, set_setting
from models import (MonitorDecision, PLATFORM_TYPES, RULE_OBJECTS, METRICS, OPERATORS,
                    ACTIONS, TIME_RANGES, SCHEDULE_FREQUENCIES)
from services.accounts import list_accounts, get_account, create_account, update_account, delete_account
from services.redtrack import RedTrackClient, get_mock_campaigns
from services.rules import (list_rules, create_rule, update_rule, delete_rule, get_rule,
    find_matching_action, save_log, list_logs, clear_monitor_results, save_monitor_result, list_monitor_results)
from services.platforms import execute_action
from services.notify import notify_rule_triggered
from services.scheduler import scheduler

app = FastAPI(title="RedTrack Rules Engine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
init_db()


def get_dry_run():
    return get_setting("dry_run", "true").lower() == "true"

def _ctx(request, page):
    return {"request": request, "page": page, "dry_run": get_dry_run(),
            "redtrack_api_key": get_setting("redtrack_api_key",""),
            "scheduler_status": scheduler.status,
            "accounts": list_accounts(), "platform_types": PLATFORM_TYPES}


def fetch_all_data():
    accounts = list_accounts(active_only=True)
    rt_key = get_setting("redtrack_api_key", "")
    all_data, source = [], "mock"

    if rt_key and rt_key != "COLE_SUA_API_KEY_AQUI":
        try:
            client = RedTrackClient(api_key=rt_key)
            all_data = client.fetch_report()
            source = "api"
            save_log("INFO", "fetch_data", f"RedTrack API: {len(all_data)} objects")
        except Exception as e:
            save_log("WARNING", "fetch_fallback", f"RT API error: {e}")

    if not all_data:
        all_data = get_mock_campaigns(accounts)
        source = "mock"

    return all_data, source, accounts


def run_monitoring():
    dry_run = get_dry_run()
    rules = list_rules()
    all_data, source, accounts = fetch_all_data()
    acc_map = {a.id: a for a in accounts}
    clear_monitor_results()
    decisions = []

    for obj in all_data:
        acc = acc_map.get(obj.ad_account_id)
        owner = acc.owner if acc else ""
        match = find_matching_action(obj, rules)

        if match:
            rule, action = match
            action_label = action.describe_action()

            if action.action == "notification":
                status = "NOTIFIED"
            elif dry_run:
                status = "DRY_RUN"
                save_log("WARNING", "dry_run", f"Would {action_label} — DRY_RUN ON",
                         object_id=obj.object_id, object_name=obj.object_name,
                         ad_account_name=obj.ad_account_name, platform=obj.platform,
                         owner=owner, cost=obj.cost, rule_name=rule.name)
            else:
                try:
                    if acc and acc.has_api() and action.action != "notification":
                        # Build a fake TeamMember-like object for platforms.py
                        from models import AdAccount
                        execute_action(acc, obj.platform, obj.object_type, obj.platform_id,
                                       action.action, action.scale_value)
                    status = {"pause":"PAUSED","pause_restart":"PAUSED"}.get(action.action, "ACTED")
                    save_log("INFO", action.action, f"Executed: {action_label}",
                             object_id=obj.object_id, object_name=obj.object_name,
                             ad_account_name=obj.ad_account_name, platform=obj.platform,
                             owner=owner, cost=obj.cost, rule_name=rule.name)
                except Exception as e:
                    status = "ERROR"
                    save_log("ERROR", "execute_error", f"Error: {e}",
                             object_id=obj.object_id, object_name=obj.object_name,
                             ad_account_name=obj.ad_account_name, platform=obj.platform,
                             owner=owner, cost=obj.cost, rule_name=rule.name)

            if rule.notify_email or rule.notify_webhook:
                try:
                    notify_rule_triggered(rule.name, action_label, obj.object_name, obj.object_id,
                        obj.platform, owner, {"cost":obj.cost,"revenue":obj.revenue,"roi":obj.roi},
                        rule.notify_email, rule.notify_webhook)
                except: pass
            matched_rule, matched_action = rule.name, action_label
        else:
            status, matched_rule, matched_action = "OK", None, None

        d = MonitorDecision(object_id=obj.object_id, object_name=obj.object_name,
            object_type=obj.object_type, ad_account_name=obj.ad_account_name,
            platform=obj.platform, owner=owner, platform_id=obj.platform_id,
            cost=obj.cost, revenue=obj.revenue, roi=obj.roi,
            matched_rule=matched_rule, matched_action=matched_action, pause_status=status)
        save_monitor_result(d)
        decisions.append(d)

    return decisions, {"total":len(decisions),
        "matched":len([d for d in decisions if d.matched_rule]),
        "acted":len([d for d in decisions if d.pause_status!="OK"]),
        "source":source, "dry_run":dry_run}


# ═══ ROUTES ═══════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    results = list_monitor_results(200)
    ctx = _ctx(request, "dashboard")
    ctx.update({"rules_count": len(list_rules()),
        "total_objects": len(results),
        "matched_count": len([r for r in results if r["matched_rule"]]),
        "acted_count": len([r for r in results if r["pause_status"]!="OK"]),
        "results": results, "logs": list_logs(20)})
    return templates.TemplateResponse("index.html", ctx)

# ─── Ad Accounts (Traffic Channels) ─────────────────────────────
@app.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request):
    ctx = _ctx(request, "accounts")
    ctx["editing"] = None
    return templates.TemplateResponse("accounts.html", ctx)

@app.get("/accounts/{aid}/edit", response_class=HTMLResponse)
def accounts_edit(request: Request, aid: int):
    ctx = _ctx(request, "accounts")
    ctx["editing"] = get_account(aid)
    return templates.TemplateResponse("accounts.html", ctx)

@app.post("/api/accounts/save")
async def api_accounts_save(request: Request):
    body = await request.json()
    aid = body.pop("id", None)
    if aid:
        update_account(aid, body)
        save_log("INFO", "update_account", f"Account updated: {body['name']}", ad_account_name=body["name"])
    else:
        aid = create_account(body)
        save_log("INFO", "create_account", f"Account created: {body['name']}", ad_account_name=body["name"])
    return JSONResponse({"ok": True, "id": aid})

@app.post("/accounts/{aid}/delete")
def accounts_delete(aid: int):
    a = get_account(aid)
    delete_account(aid)
    save_log("WARNING", "delete_account", f"Account removed: {a.name if a else '?'}")
    return RedirectResponse(url="/accounts", status_code=303)

# ─── Rules ───────────────────────────────────────────────────────
@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    ctx = _ctx(request, "rules")
    ctx.update({"rules": list_rules(), "editing_rule": None, "editing_rule_json": "null",
        "rule_objects": RULE_OBJECTS, "metrics": METRICS, "operators": OPERATORS,
        "actions": ACTIONS, "time_ranges": TIME_RANGES, "schedule_frequencies": SCHEDULE_FREQUENCIES})
    return templates.TemplateResponse("rules.html", ctx)

@app.get("/rules/{rule_id}/edit", response_class=HTMLResponse)
def edit_rule(request: Request, rule_id: int):
    editing = get_rule(rule_id)
    ctx = _ctx(request, "rules")
    ctx.update({"rules": list_rules(), "editing_rule": editing,
        "editing_rule_json": json.dumps({
            "id": editing.id, "name": editing.name,
            "ad_account_ids": editing.ad_account_ids,
            "rule_object": editing.rule_object, "campaign_filter": editing.campaign_filter,
            "schedule_minutes": editing.schedule_minutes,
            "notify_email": editing.notify_email, "notify_webhook": editing.notify_webhook,
            "active": editing.active,
            "actions": [{"action":a.action,"scale_value":a.scale_value,
                "conditions":[{"metric":c.metric,"operator":c.operator,"value":c.value,"time_range":c.time_range}
                    for c in a.conditions]} for a in editing.actions]
        }) if editing else "null",
        "rule_objects": RULE_OBJECTS, "metrics": METRICS, "operators": OPERATORS,
        "actions": ACTIONS, "time_ranges": TIME_RANGES, "schedule_frequencies": SCHEDULE_FREQUENCIES})
    return templates.TemplateResponse("rules.html", ctx)

@app.post("/api/rules/save")
async def api_save_rule(request: Request):
    b = await request.json()
    kw = dict(name=b["name"], ad_account_ids=b["ad_account_ids"], rule_object=b["rule_object"],
              campaign_filter=b.get("campaign_filter",""), actions_data=b.get("actions",[]),
              schedule_minutes=int(b.get("schedule_minutes",5)),
              notify_email=b.get("notify_email",""), notify_webhook=b.get("notify_webhook",""),
              active=bool(b.get("active",True)))
    rid = b.get("id")
    if rid: update_rule(rid, **kw); return JSONResponse({"ok":True,"rule_id":rid})
    else: return JSONResponse({"ok":True,"rule_id":create_rule(**kw)})

@app.post("/rules/{rule_id}/delete")
def rules_delete(rule_id: int):
    r = get_rule(rule_id)
    delete_rule(rule_id)
    save_log("WARNING","delete_rule","Rule removed",rule_name=r.name if r else None)
    return RedirectResponse(url="/rules", status_code=303)

# ─── Logs ────────────────────────────────────────────────────────
@app.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    ctx = _ctx(request, "logs")
    ctx["logs"] = list_logs(200)
    return templates.TemplateResponse("logs.html", ctx)

# ─── Monitor / Pause / Settings / Scheduler ──────────────────────
@app.post("/monitor/run")
def monitor_run():
    decisions, summary = run_monitoring()
    return JSONResponse({"ok":True,"summary":summary,"results":[d.__dict__ for d in decisions]})

@app.post("/api/objects/{oid}/pause")
async def pause_manual(oid: str, request: Request):
    body = await request.json()
    dry_run = get_dry_run()
    try:
        if dry_run:
            save_log("WARNING","manual_pause","DRY_RUN simulated",object_id=oid,object_name=body.get("object_name"))
            return JSONResponse({"ok":True,"status":"DRY_RUN"})
        save_log("INFO","manual_pause","Paused manually",object_id=oid,object_name=body.get("object_name"))
        return JSONResponse({"ok":True,"status":"PAUSED"})
    except Exception as e:
        return JSONResponse({"ok":False,"error":str(e)}, status_code=500)

@app.post("/settings/dry-run")
def toggle_dry_run(enabled: str = Form(...)):
    set_setting("dry_run", "true" if enabled=="true" else "false")
    save_log("INFO","toggle_dry_run",f"DRY_RUN → {enabled}")
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/settings/redtrack-key")
async def save_rt_key(request: Request):
    body = await request.json()
    set_setting("redtrack_api_key", body.get("api_key","").strip())
    save_log("INFO","update_rt_key","RedTrack API key updated")
    return JSONResponse({"ok":True})

@app.post("/api/scheduler/start")
async def sched_start(request: Request):
    body = await request.json()
    i = int(body.get("interval_minutes",5))
    scheduler.start(callback=run_monitoring, interval_minutes=i)
    save_log("INFO","scheduler_start",f"Started every {i}min")
    return JSONResponse({"ok":True,"status":scheduler.status})

@app.post("/api/scheduler/stop")
def sched_stop():
    scheduler.stop()
    save_log("INFO","scheduler_stop","Stopped")
    return JSONResponse({"ok":True,"status":scheduler.status})

@app.get("/api/scheduler/status")
def sched_status():
    return JSONResponse(scheduler.status)
