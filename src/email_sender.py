import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


def send_report_email(pdf_path: str, date_str: str, html_path: Optional[str] = None) -> None:
    """
    Invia il report PDF via email usando SMTP.
    Legge i parametri dalle variabili di ambiente (settate via GitHub Secrets):

    SMTP_HOST
    SMTP_PORT
    SMTP_USER
    SMTP_PASSWORD
    TO_EMAIL
    FROM_EMAIL  (opzionale, se non presente usa SMTP_USER)

    Qualsiasi errore viene loggato ma NON lancia eccezioni, così il job non fallisce.
    """

    # Porta SMTP – parsing sicuro
    port_str = os.getenv("SMTP_PORT") or "587"
    try:
        smtp_port = int(port_str)
    except ValueError:
        print(f"[EMAIL] Invalid SMTP_PORT value: {port_str!r}. Email not sent.")
        return

    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    to_email = os.getenv("TO_EMAIL")
    from_email = os.getenv("FROM_EMAIL") or (smtp_user or "")

    if not smtp_host or not smtp_user or not smtp_password or not to_email:
        print("[EMAIL] Missing SMTP configuration. Email not sent.")
        print("        Required: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, TO_EMAIL")
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
    try:
        with open(pdf_file, "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(
            pdf_data,
            maintype="application",
            subtype="pdf",
            filename=pdf_file.name,
        )
    except Exception as e:
        print("[EMAIL] Failed to attach PDF:", repr(e))
        return

    # (opzionale) allego anche l'HTML
    if html_path:
        html_file = Path(html_path)
        if html_file.exists():
            try:
                with open(html_file, "rb") as f:
                    html_data = f.read()
                msg.add_attachment(
                    html_data,
                    maintype="text",
                    subtype="html",
                    filename=html_file.name,
                )
            except Exception as e:
                print("[EMAIL] Failed to attach HTML:", repr(e))

    print(f"[EMAIL] Connecting to SMTP {smtp_host}:{smtp_port} as {smtp_user}...")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"[EMAIL] Report sent to {to_email}")
    except Exception as e:
        print("[EMAIL] Failed to send email:", repr(e))
        # NON rialziamo l’eccezione: il job deve comunque passare
        return
