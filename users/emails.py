"""
Email helpers for the users app.

All HTML + plain-text bodies are embedded here — no template folders,
no .html files on disk.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


# ============================================================
# SHARED HELPERS
# ============================================================
def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _support_email() -> str:
    return getattr(settings, "EMAIL_HOST_USER", "")


def _build_verify_link(token: str) -> str:
    return f"{_frontend_url()}/acc-verify?token={token}"


def _send(subject: str, to_email: str, text: str, html: str, ref: str = "") -> int:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
        headers={"X-Entity-Ref-ID": ref} if ref else None,
    )
    msg.attach_alternative(html, "text/html")
    return msg.send(fail_silently=False)


# ============================================================
# 1. REGISTRATION VERIFICATION EMAIL
# ============================================================
VERIFY_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Verify your Tesla Cloud Institute account</title>
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f4f5;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px; width:100%; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
          <tr>
            <td align="center" style="background:#000000; padding:32px 24px;">
              <div style="color:#ffffff; font-size:20px; font-weight:700; letter-spacing:2px;">
                TESLA CLOUD INSTITUTE
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:40px 32px 24px 32px;">
              <h1 style="margin:0 0 16px 0; font-size:24px; color:#111827; font-weight:700;">
                Welcome, {full_name}!
              </h1>
              <p style="margin:0 0 16px 0; font-size:15px; line-height:1.6; color:#374151;">
                Your Tesla Cloud Institute account has been created successfully.
                Here are your login details:
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; margin:16px 0 24px 0;">
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0 0 6px 0; font-size:12px; text-transform:uppercase; letter-spacing:1px; color:#6b7280; font-weight:600;">
                      Username
                    </p>
                    <p style="margin:0 0 16px 0; font-size:18px; font-family: 'Courier New', monospace; font-weight:700; color:#111827;">
                      {username}
                    </p>
                    <p style="margin:0; font-size:13px; color:#6b7280;">
                      Use this username (or the email you registered with) to sign in.
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 24px 0; font-size:15px; line-height:1.6; color:#374151;">
                To activate your account, please verify your email by clicking
                the button below. This link expires in <strong>2 days</strong>.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto 24px auto;">
                <tr>
                  <td align="center" style="background:#000000; border-radius:8px;">
                    <a href="{verify_link}"
                       style="display:inline-block; padding:14px 36px; color:#ffffff; font-size:15px; font-weight:600; text-decoration:none; letter-spacing:0.5px;">
                      Verify My Account
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 8px 0; font-size:13px; color:#6b7280;">
                Or copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px 0; font-size:13px; word-break:break-all;">
                <a href="{verify_link}" style="color:#2563eb; text-decoration:underline;">
                  {verify_link}
                </a>
              </p>
              <p style="margin:0; font-size:13px; color:#6b7280;">
                If you didn't create this account, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background:#f9fafb; padding:20px 32px; border-top:1px solid #e5e7eb;">
              <p style="margin:0 0 6px 0; font-size:12px; color:#6b7280; text-align:center;">
                Need help? Contact us at
                <a href="mailto:{support_email}" style="color:#2563eb; text-decoration:none;">
                  {support_email}
                </a>
              </p>
              <p style="margin:0; font-size:11px; color:#9ca3af; text-align:center;">
                &copy; Tesla Cloud Institute &mdash; Empowering the next generation of technologists.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

VERIFY_EMAIL_TEXT = """\
Welcome to Tesla Cloud Institute, {full_name}!

Your account has been created successfully.

----------------------------------------
USERNAME: {username}
----------------------------------------

To activate your account, please verify your email by opening the link below.
This link expires in 2 days.

{verify_link}

If you didn't create this account, you can safely ignore this email.

Need help? Contact us at {support_email}

(c) Tesla Cloud Institute
"""


def send_registration_verification_email(
    *,
    to_email: str,
    full_name: str,
    username: str,
    token: str,
) -> int:
    """Send the 'verify your Tesla Cloud account' email."""
    ctx = {
        "full_name": full_name or "Student",
        "username": username,
        "verify_link": _build_verify_link(token),
        "support_email": _support_email(),
    }
    return _send(
        subject="Verify your Tesla Cloud Institute account",
        to_email=to_email,
        text=VERIFY_EMAIL_TEXT.format(**ctx),
        html=VERIFY_EMAIL_HTML.format(**ctx),
        ref=username,
    )


# ============================================================
# 2. PASSWORD RESET CODE EMAIL
# ============================================================
RESET_CODE_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Your Tesla Cloud password reset code</title>
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f4f5;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px; width:100%; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
          <tr>
            <td align="center" style="background:#000000; padding:32px 24px;">
              <div style="color:#ffffff; font-size:20px; font-weight:700; letter-spacing:2px;">
                TESLA CLOUD INSTITUTE
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:40px 32px;">
              <h1 style="margin:0 0 16px 0; font-size:22px; color:#111827; font-weight:700;">
                Password Reset Code
              </h1>
              <p style="margin:0 0 16px 0; font-size:15px; line-height:1.6; color:#374151;">
                Hi {full_name}, we received a request to reset your password.
                Use the code below to continue.
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:24px; text-align:center; margin:16px 0 24px 0;">
                <tr>
                  <td style="padding:24px;">
                    <p style="margin:0 0 8px 0; font-size:12px; text-transform:uppercase; letter-spacing:1px; color:#6b7280; font-weight:600;">
                      Your code
                    </p>
                    <p style="margin:0; font-size:36px; font-family: 'Courier New', monospace; font-weight:700; letter-spacing:8px; color:#111827;">
                      {code}
                    </p>
                    <p style="margin:12px 0 0 0; font-size:12px; color:#6b7280;">
                      Expires in 15 minutes
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 16px 0; font-size:13px; color:#6b7280;">
                If you didn't request this, you can safely ignore this email —
                your password will not change.
              </p>
              <p style="margin:0; font-size:13px; color:#6b7280;">
                For your security, never share this code with anyone.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background:#f9fafb; padding:20px 32px; border-top:1px solid #e5e7eb;">
              <p style="margin:0 0 6px 0; font-size:12px; color:#6b7280; text-align:center;">
                Need help? Contact us at
                <a href="mailto:{support_email}" style="color:#2563eb; text-decoration:none;">
                  {support_email}
                </a>
              </p>
              <p style="margin:0; font-size:11px; color:#9ca3af; text-align:center;">
                &copy; Tesla Cloud Institute &mdash; Empowering the next generation of technologists.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

RESET_CODE_EMAIL_TEXT = """\
Password Reset Code — Tesla Cloud Institute

Hi {full_name},

We received a request to reset your password. Use the code below:

    {code}

This code expires in 15 minutes.

If you didn't request this, you can safely ignore this email — your
password will not change.

For your security, never share this code with anyone.

Need help? Contact us at {support_email}

(c) Tesla Cloud Institute
"""


def send_password_reset_code_email(
    *,
    to_email: str,
    full_name: str,
    code: str,
) -> int:
    """Send the password reset 6-digit code."""
    ctx = {
        "full_name": full_name or "Student",
        "code": code,
        "support_email": _support_email(),
    }
    return _send(
        subject="Your Tesla Cloud password reset code",
        to_email=to_email,
        text=RESET_CODE_EMAIL_TEXT.format(**ctx),
        html=RESET_CODE_EMAIL_HTML.format(**ctx),
    )