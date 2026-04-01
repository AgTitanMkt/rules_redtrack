import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "rules@dashboard.local")


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not to_email:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[NOTIFY] Email error: {e}")
        return False


def send_webhook(webhook_url: str, payload: dict) -> bool:
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json=payload,
                             headers={"Content-Type": "application/json"}, timeout=10)
        return resp.status_code < 400
    except Exception as e:
        print(f"[NOTIFY] Webhook error: {e}")
        return False


def notify_rule_triggered(rule_name, action_label, object_name, object_id,
                          traffic_channel, member_name, metrics,
                          notify_email="", notify_webhook=""):
    subject = f"[Rules] {action_label}: {object_name}"
    body = f"""
    <div style="font-family:sans-serif;max-width:600px;">
        <h2 style="color:#ef4444;">Rule: {rule_name}</h2>
        <table style="border-collapse:collapse;width:100%;">
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Action</b></td><td style="padding:6px;border-bottom:1px solid #eee;">{action_label}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Object</b></td><td style="padding:6px;border-bottom:1px solid #eee;">{object_name}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Channel</b></td><td style="padding:6px;border-bottom:1px solid #eee;">{traffic_channel}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Member</b></td><td style="padding:6px;border-bottom:1px solid #eee;">{member_name}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Cost</b></td><td style="padding:6px;border-bottom:1px solid #eee;">${metrics.get('cost',0):.2f}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>Revenue</b></td><td style="padding:6px;border-bottom:1px solid #eee;">${metrics.get('revenue',0):.2f}</td></tr>
            <tr><td style="padding:6px;border-bottom:1px solid #eee;"><b>ROI</b></td><td style="padding:6px;border-bottom:1px solid #eee;">{metrics.get('roi',0):.1f}%</td></tr>
        </table>
    </div>"""

    payload = {"event": "rule_triggered", "rule_name": rule_name, "action": action_label,
               "object_name": object_name, "object_id": object_id,
               "traffic_channel": traffic_channel, "member": member_name, "metrics": metrics}

    if notify_email:
        for em in notify_email.split(","):
            em = em.strip()
            if em:
                send_email(em, subject, body)
    if notify_webhook:
        send_webhook(notify_webhook, payload)
