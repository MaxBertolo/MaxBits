import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_report_email(pdf_path: str, date_str: str, html_path: str | None = None) -> None:
    """
    Invia il report via SMTP (pensato per Gmail).

    Legge le variabili d'ambiente:
      - SMTP_HOST (default: smtp.gmail.com)
      - SMTP_PORT (default: 587)
      - SMTP_USER (OBBLIGATORIA)
      - SMTP_PASSWORD (OBBLIGATORIA)  <-- usare APP PASSWORD Gmail
      - TO_EMAIL (OBBLIGATORIA)
      - FROM_EMAIL (opzionale, default = SMTP_USER)
    """

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_email = os.getenv("TO_EMAIL")

    if not (user and password and to_email):
        print("[EMAIL] Missing SMTP configuration. Email not sent.")
        print("[EMAIL] Required: SMTP_USER, SMTP_PASSWORD, TO_EMAIL. "
              "Optional: SMTP_HOST, SMTP_PORT, FROM_EMAIL.")
        return

    from_email = os.getenv("FROM_EMAIL", user)
    subject = f"MaxBits Daily Tech Report – {date_str}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    body_lines = [
        "Hi,",
        "",
        "Attached you can find today's MaxBits Daily Tech Report (PDF).",
        "",
        "This email was sent automatically from the GitHub Actions workflow.",
    ]
    msg.set_content("\n".join(body_lines))

    # Allego il PDF
    pdf_file = Path(pdf_path)
    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_file.name,
    )

    print(f"[EMAIL] Connecting to SMTP {host}:{port} as {user}")
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)

    print("[EMAIL] Email sent successfully.")
