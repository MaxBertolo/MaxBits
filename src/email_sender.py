import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from pathlib import Path
from typing import Tuple


def _normalize_smtp_host_and_port() -> Tuple[str, int]:
    """
    Legge SMTP_HOST / SMTP_PORT dalle env e ripulisce:
    - rimuove eventuali prefissi (smtp://, smtps://, http://, https://)
    - se c'è "host:port" nello stesso secret, li separa
    - rimuove path tipo "smtp.gmail.com:587/qualcosa"
    """
    raw_host = (os.getenv("SMTP_HOST") or "").strip()
    raw_port = (os.getenv("SMTP_PORT") or "").strip()

    host = raw_host

    # Rimuovi eventuali schemi tipo smtp://, smtps://, http://, https://
    for prefix in ("smtp://", "smtps://", "http://", "https://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix):]

    # Se c'è uno slash, tieni solo la parte prima
    if "/" in host:
        host = host.split("/", 1)[0]

    # Se c'è "host:port" nello stesso secret, separa
    if ":" in host:
        host_part, maybe_port = host.split(":", 1)
        host = host_part.strip()
        if not raw_port and maybe_port.strip().isdigit():
            raw_port = maybe_port.strip()

    # Porta di default
    if not raw_port:
        raw_port = "587"

    try:
        port = int(raw_port)
    except ValueError:
        print(f"[EMAIL] Invalid SMTP_PORT '{raw_port}', defaulting to 587")
        port = 587

    # Log di debug (host reale verrà mascherato da GitHub, ma vediamo almeno la lunghezza)
    print(f"[EMAIL] Raw SMTP_HOST length={len(raw_host)}, normalized host length={len(host)}, port={port}")

    return host, port


def send_report_email(pdf_path: str, date_str: str, html_path: str | None = None) -> None:
    """
    Invia il report PDF via SMTP (es. Gmail).

    Variabili d'ambiente richieste:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL, TO_EMAIL
    """
    host, port = _normalize_smtp_host_and_port()

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

    print(f"[EMAIL] Connecting to SMTP {host}:{port} as ***")

    try:
        # Se porta 465 usiamo SSL diretto, altrimenti STARTTLS (tipico 587)
        if port == 465:
            smtp_class = smtplib.SMTP_SSL
            use_starttls = False
        else:
            smtp_class = smtplib.SMTP
            use_starttls = True

        with smtp_class(host, port, timeout=30) as server:
            server.ehlo()
            if use_starttls:
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.send_message(msg)

        print("[EMAIL] Email sent successfully.")
    except Exception as e:
        # Se fallisce, non blocchiamo il job (il report è già generato)
        print("[EMAIL] Unhandled error while sending email:", repr(e))
