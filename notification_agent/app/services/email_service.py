"""
app/services/email_service.py

Asynchronous SMTP Email Delivery Service for Notification Agent.
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def send_email_sync(to_email: str, subject: str, html_body: str) -> Dict[str, Any]:
    """Synchronous SMTP email dispatcher run via asyncio.to_thread with fallback to SSL."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not str(settings.SMTP_PASSWORD).strip():
        logger.warning("SMTP credentials (password) missing in settings. Skipping email delivery.")
        return {"status": "skipped", "reason": "SMTP password not set in .env"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"AgentOS Notification Service <{settings.SMTP_USER}>"
        msg["To"] = to_email

        part_html = MIMEText(html_body, "html")
        msg.attach(part_html)

        # Attempt 1: Port 587 STARTTLS
        try:
            with smtplib.SMTP(settings.SMTP_HOST, 587, timeout=2) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
            logger.info(f"✅ Email notification sent to {to_email} via Port 587 (TLS)")
            return {"status": "success", "to": to_email}
        except Exception as t_err:
            logger.warning(f"Port 587 connection timed out or blocked: {t_err}. Trying Port 465 SSL...")
            with smtplib.SMTP_SSL(settings.SMTP_HOST, 465, timeout=2) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
            logger.info(f"✅ Email notification sent to {to_email} via Port 465 (SSL)")
            return {"status": "success", "to": to_email}

    except Exception as err:
        logger.warning(f"⚠️ SMTP Email delivery skipped for {to_email}: {err} (Network/Firewall blocks outbound SMTP ports 587/465 or Gmail App Password missing).")
        return {"status": "failed", "reason": "Network/Firewall blocks outbound SMTP ports 587/465 or Gmail App Password missing."}


async def send_notification_email(
    to_email: str,
    title: str,
    description: str,
    priority: str,
    notification_type: str,
    action_url: str = None,
    actions: list = None
) -> Dict[str, Any]:
    """Asynchronous wrapper for email delivery with rich HTML template."""

    target_email = to_email if to_email and "@" in to_email else settings.SMTP_USER

    priority_colors = {
        "Emergency": "#ef4444",
        "High": "#f97316",
        "Medium": "#0ea5e9",
        "Low": "#10b981"
    }
    p_color = priority_colors.get(priority, "#0ea5e9")

    actions_html = ""
    if actions:
        buttons = []
        for act in actions:
            link = action_url if action_url else "#"
            buttons.append(
                f'<a href="{link}" style="display:inline-block; background:{p_color}; color:#ffffff; padding:10px 18px; margin:4px; text-decoration:none; border-radius:6px; font-weight:bold; font-size:13px;">{act}</a>'
            )
        actions_html = f'<div style="margin-top:20px;">{"".join(buttons)}</div>'

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #050b14; color: #f8fafc; margin: 0; padding: 20px; }}
            .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; max-width: 600px; margin: 0 auto; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; }}
            .brand {{ font-size: 18px; font-weight: bold; color: #38bdf8; }}
            .priority-badge {{ background: {p_color}22; color: {p_color}; border: 1px solid {p_color}; font-size: 11px; font-weight: bold; padding: 4px 10px; border-radius: 20px; text-transform: uppercase; }}
            .title {{ font-size: 20px; font-weight: bold; color: #ffffff; margin-top: 0; margin-bottom: 8px; }}
            .type {{ font-size: 12px; color: #94a3b8; margin-bottom: 16px; text-transform: uppercase; font-weight: 600; }}
            .desc {{ font-size: 14px; color: #cbd5e1; line-height: 1.6; background: #020617; padding: 16px; border-radius: 8px; border-left: 4px solid {p_color}; }}
            .footer {{ font-size: 11px; color: #64748b; margin-top: 24px; text-align: center; border-top: 1px solid #1e293b; padding-top: 12px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <span class="brand">AgentOS Notification Agent</span>
                <span class="priority-badge">{priority} Priority</span>
            </div>
            <div class="type">Type: {notification_type}</div>
            <h2 class="title">{title}</h2>
            <div class="desc">{description}</div>
            {actions_html}
            <div class="footer">
                Delivered autonomously by AgentOS Notification Agent &bull; {settings.SERVICE_NAME} v{settings.VERSION}
            </div>
        </div>
    </body>
    </html>
    """

    subject = f"[{priority.upper()}] AgentOS Notification: {title}"

    return await asyncio.to_thread(send_email_sync, target_email, subject, html_template)
