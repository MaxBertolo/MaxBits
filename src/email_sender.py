import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_report_email(pdf_path: str, date_str: str, html_path: str | None = None):
    """
    Invia il report PDF via email usando SMTP.
    Legge i parametri dal contesto (variabili di ambiente):

    SMTP_HOST
    SMTP_PORT
    SMTP_USER
    SMTP_PASSWORD
    TO_EMAIL
    FROM_EMAIL  (opzionale, se non presente usa SMTP_USER)
    """

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    to_email = os.getenv("TO_EMAIL")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password, to_email]):
        print("[EMAIL] Missing SMTP configuration. Email not sent.")
        print("[EMAIL] Required: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, TO_EMAIL")
        return

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"[EMAIL] PDF file not found: {pdf_file}")
        return

    subject = f"MaxBits – Daily Tech Report – {date_str}"
    body_lines = [
        "Ciao,",
        "",
        "in allegato trovi il report MaxBits di oggi.",
        "",
        f"Data: {date_str}",
        "",
        "Questo messaggio è generato automaticamente dal workflow GitHub Actions.",
        "",
        "--",
        "MaxBits Bot",
    ]
    body = "\n".join(body_lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    # Allego il PDF
    with open(pdf_file, "rb") as f:
        pdf_data = f.read()
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=pdf_file.name,
    )

    # (opzionale) allego anche l'HTML se lo passi
    if html_path:
        html_file = Path(html_path)
        if html_file.exists():
            with open(html_file, "rb") as f:
                html_data = f.read()
            msg.add_attachment(
                html_data,
                maintype="text",
                subtype="html",
                filename=html_file.name,
            )

    print(f"[EMAIL] Connecting to SMTP {smtp_host}:{smtp_port} as {smtp_user}...")

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[EMAIL] Report sent to {to_email}")
    except Exception as e:
        print("[EMAIL] Failed to send email:", repr(e))

