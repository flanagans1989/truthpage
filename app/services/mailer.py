import asyncio
import html
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


class MailerService:
    async def _send(self, to: str, subject: str, html: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    _RESEND_API_URL,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json={"from": settings.RESEND_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
                )
                resp.raise_for_status()
                logger.info("mailer: sent '%s' to %s (status=%s)", subject, to, resp.status_code)
        except Exception:
            logger.exception("mailer: failed to send '%s' to %s", subject, to)

    async def send_magic_link(self, email: str, link: str) -> None:
        subject = "Your TrustPages sign-in link"
        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sign in to TrustPages</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="padding:48px 16px;">
    <tr><td align="center">

      <!-- Card -->
      <table role="presentation" width="520" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;max-width:520px;">

        <!-- Header bar -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);padding:32px 40px;">
            <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td>
                  <span style="display:inline-block;background:rgba(255,255,255,0.15);
                               border-radius:8px;padding:6px 10px;font-size:18px;line-height:1;">
                    &#128274;
                  </span>
                </td>
                <td style="padding-left:12px;vertical-align:middle;">
                  <span style="font-size:18px;font-weight:800;color:#ffffff;letter-spacing:-0.3px;">
                    TrustPages
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 0;">
            <p style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;letter-spacing:-0.3px;">
              Your sign-in link is ready
            </p>
            <p style="margin:0 0 32px;font-size:14px;color:#64748b;line-height:1.7;">
              Click the button below to sign in to your TrustPages account.
              This link is valid for <strong>15 minutes</strong> and can only be used once.
            </p>

            <!-- CTA Button -->
            <table role="presentation" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-radius:10px;background:#2563eb;">
                  <a href="{link}"
                     style="display:inline-block;padding:15px 32px;font-size:15px;font-weight:700;
                            color:#ffffff;text-decoration:none;letter-spacing:0.1px;">
                    Sign in to TrustPages &rarr;
                  </a>
                </td>
              </tr>
            </table>

            <!-- Fallback link -->
            <p style="margin:24px 0 0;font-size:12px;color:#94a3b8;line-height:1.6;">
              Button not working?
              <a href="{link}" style="color:#2563eb;word-break:break-all;">Copy this link</a>
            </p>
          </td>
        </tr>

        <!-- Divider + Security note -->
        <tr>
          <td style="padding:32px 40px 0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-top:1px solid #f1f5f9;padding-top:24px;">
                  <table role="presentation" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="vertical-align:top;padding-right:10px;font-size:16px;">&#128737;</td>
                      <td style="font-size:12px;color:#94a3b8;line-height:1.6;">
                        <strong style="color:#64748b;">Security notice</strong><br>
                        TrustPages will never ask for your password. If you didn't request this
                        email, you can safely ignore it — your account remains secure.
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:24px 40px 32px;">
            <p style="margin:0;font-size:11px;color:#cbd5e1;line-height:1.5;">
              &copy; 2025 TrustPages &bull; Privacy policy sub-processor monitoring
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send(email, subject, body)

    async def send_subscription_confirmation(
        self, email: str, link: str, tenant_name: str
    ) -> None:
        subject = f"Confirm your subscription to {tenant_name}"
        html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:48px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:48px 40px;">
        <tr><td>
          <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">
            {tenant_name}
          </p>
          <p style="margin:0 0 8px;font-size:20px;font-weight:700;color:#0f172a;">
            Confirm your subscription
          </p>
          <p style="margin:0 0 32px;font-size:14px;color:#64748b;line-height:1.6;">
            You asked to be notified whenever <strong>{tenant_name}</strong> updates their
            sub-processor list or data processing agreements. Click below to confirm.
          </p>
          <a href="{link}"
             style="display:inline-block;background:#2563eb;color:#ffffff;font-size:14px;
                    font-weight:600;padding:14px 28px;border-radius:8px;text-decoration:none;">
            Confirm Subscription
          </a>
          <p style="margin:32px 0 0;font-size:12px;color:#94a3b8;line-height:1.5;">
            If you didn't request this, no action is needed — you won't receive any emails.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        await self._send(email, subject, html)

    async def send_change_notification(
        self,
        recipients: list[tuple[str, str]],  # (email, unsubscribe_url)
        tenant_name: str,
        subprocessor_name: str,
        summary: str,
    ) -> None:
        subject = f"[{tenant_name}] Sub-processor change detected: {subprocessor_name}"

        safe_tenant = html.escape(tenant_name)
        safe_name = html.escape(subprocessor_name)
        safe_summary = html.escape(summary)

        def _build_html(unsubscribe_url: str) -> str:
            return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:48px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:48px 40px;">
        <tr><td>
          <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">
            Data Processing Update
          </p>
          <p style="margin:0 0 24px;font-size:20px;font-weight:700;color:#0f172a;">
            {safe_tenant} updated their sub-processor list
          </p>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f1f5f9;border-radius:8px;padding:20px;margin-bottom:24px;">
            <tr><td>
              <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;">
                Sub-processor
              </p>
              <p style="margin:0 0 16px;font-size:16px;font-weight:700;color:#0f172a;">{safe_name}</p>
              <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;">
                What changed
              </p>
              <p style="margin:0;font-size:14px;color:#334155;line-height:1.6;">{safe_summary}</p>
            </td></tr>
          </table>
          <p style="margin:0 0 16px;font-size:12px;color:#94a3b8;line-height:1.5;">
            You're receiving this because you subscribed to updates from {safe_tenant}.
            This change has been reviewed and approved by their privacy team.
          </p>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            <a href="{unsubscribe_url}" style="color:#94a3b8;">Unsubscribe</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        tasks = [self._send(email, subject, _build_html(url)) for email, url in recipients]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        sent = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(
            "mailer: change_notification sent %d/%d for subprocessor '%s'",
            sent, len(recipients), subprocessor_name,
        )


mailer = MailerService()
