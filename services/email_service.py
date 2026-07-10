import httpx

from config import settings

RESEND_ENDPOINT = "https://api.resend.com/emails"


def email_configured() -> bool:
    """True when an email provider (Resend) is set up.

    When this is False the auth flow skips real sending and surfaces the OTP
    directly (dev_otp) so testing isn't blocked.
    """
    return bool(settings.RESEND_API_KEY)


def _otp_email_html(full_name: str, otp: str) -> str:
    name = full_name or "there"
    return f"""\
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 480px; margin: 0 auto; color: #0F172A;">
  <h2 style="color: #1B3A6B; margin-bottom: 8px;">Verify your email</h2>
  <p style="margin: 0 0 16px;">Hi {name},</p>
  <p style="margin: 0 0 16px;">
    Use the verification code below to finish setting up your
    {settings.FROM_NAME} account. This code expires in 10 minutes.
  </p>
  <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
              color: #2563EB; background: #EFF6FF; padding: 16px 0;
              text-align: center; border-radius: 8px; margin: 0 0 16px;">
    {otp}
  </div>
  <p style="margin: 0; font-size: 13px; color: #64748B;">
    If you didn't request this, you can safely ignore this email.
  </p>
</div>"""


async def send_verification_email(email: str, full_name: str, otp: str) -> None:
    """Send a verification OTP to the user via Resend.

    No-op when email isn't configured, so registration can still proceed with
    a dev_otp. Raises on a genuine send failure; the caller rolls back and
    surfaces the error.
    """
    if not email_configured():
        return

    sender = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
    payload = {
        "from": sender,
        "to": [email],
        "subject": f"Your {settings.FROM_NAME} verification code",
        "html": _otp_email_html(full_name, otp),
    }
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(RESEND_ENDPOINT, json=payload, headers=headers)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Resend API returned {response.status_code}: {response.text}"
        )
