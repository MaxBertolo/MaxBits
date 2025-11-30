# src/email_sender.py
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from pathlib import Path


def send_report_email(pdf_path: str, date_str: str, html_path: str | None = None) -> None:
    """
    Invia il report PDF via SMTP (Gmail).

    Usa variabili d'ambiente:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL, TO_EMAIL
    """
    host = (os.getenv("SMTP_HOST") or "").strip()
    port_str = (os.getenv("SMTP_PORT") or "").strip() or "587"
    user = (os.getenv("SMTP_USER") or "").strip()
    password = os.getenv("SMTP_PASSWORD") or ""
    from_email = (os.getenv("FROM_EMAIL") or user).strip()
    to_email = (os.getenv("TO_EMAIL") or user).strip()

    if not host or not user or not password or not to_email:
        print(
            "[EMAIL] Missing SMTP configuration. Email not sent.\n"
            "        Required: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, TO_EMAIL"
        )
        return

    try:
        port = int(port_str)
    except ValueError:
        print(f"[EMAIL] Invalid SMTP_PORT '{port_str}', defaulting to 587")
        port = 587

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"[EMAIL] PDF file not found: {pdf_file}")
        return

    subject = f"MaxBits Daily Tech Report – {date_str}"
    body_text = (
        f"Hi,\n\n"
        f"Your MaxBits Daily Tech Report for {date_str} is attached as PDF.\n\n"
        f"Regards,\nMaxBits bot"
    )

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    with open(pdf_file, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=pdf_file.name)
        msg.attach(part)

    # Log "censurato" ma sufficiente per capire che host/port non sono vuoti
    print(f"[EMAIL] Connecting to SMTP {host}:{port} as ***")

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        print("[EMAIL] Email sent successfully.")
    except Exception as e:
        print("[EMAIL] Unhandled error while sending email:", repr(e))
