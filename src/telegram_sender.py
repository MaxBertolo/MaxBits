import os
import requests
from pathlib import Path


def send_telegram_pdf(pdf_path: str, date_str: str) -> None:
    """
    Send the generated PDF report to a Telegram chat using a bot.

    Required environment variables (set as GitHub Actions secrets):
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_CHAT_ID
    """
    bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not bot_token or not chat_id:
        print("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping Telegram step.")
        return

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"[TELEGRAM] PDF file not found: {pdf_file}")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    print(f"[TELEGRAM] Sending '{pdf_file.name}' to chat_id={chat_id}...")
    try:
        with open(pdf_file, "rb") as f:
            files = {"document": (pdf_file.name, f, "application/pdf")}
            data = {
                "chat_id": chat_id,
                "caption": f"MaxBits Daily Tech Report – {date_str}",
            }

            response = requests.post(url, data=data, files=files, timeout=60)
            print("[TELEGRAM] Status:", response.status_code)
            print("[TELEGRAM] Response:", response.text)

            if response.status_code != 200:
                print("[TELEGRAM] Warning: Telegram API did not return 200 OK.")
    except Exception as e:
        print("[TELEGRAM] Unhandled error while sending PDF:", repr(e))
        print("[TELEGRAM] Continuing – report generation already completed.")
