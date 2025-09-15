# healthbot/worker/alert_worker.py
import os
import sqlite3
import logging
from datetime import datetime
from twilio.rest import Client
from apscheduler.schedulers.blocking import BlockingScheduler

# Paths
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE, "db", "healthbot.db")

# Twilio config (set these in Render / .env locally)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")          # e.g. +1234567890 (SMS)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")       # e.g. whatsapp:+14155238886 (recommended)

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise RuntimeError("Twilio credentials not set in env variables.")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
scheduler = BlockingScheduler()

def _connect():
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)

def send_message(to_number: str, body: str):
    """
    to_number should be either:
    - 'whatsapp:+9199...' (for WhatsApp)
    - '+9199...' (for SMS)
    """
    # decide from_ based on to_number format
    if to_number.startswith("whatsapp:"):
        from_number = TWILIO_WHATSAPP_FROM or f"whatsapp:{TWILIO_PHONE_NUMBER}"
    else:
        from_number = TWILIO_PHONE_NUMBER

    logging.info(f"Sending to {to_number} from {from_number}: {body[:80]}...")
    try:
        msg = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        logging.info(f"Sent SID {msg.sid}")
        return True
    except Exception as e:
        logging.exception("Failed to send message: %s", e)
        return False

def process_pending_broadcasts():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id, message, target_location FROM broadcasts WHERE sent = 0")
    rows = cur.fetchall()
    if not rows:
        logging.info("No pending broadcasts.")
        conn.close()
        return

    for bid, message, target_location in rows:
        logging.info(f"Processing broadcast id={bid} target={target_location}")

        # select subscribers:
        if target_location and target_location.strip():
            # send to subscribers whose alert_type matches target_location, or 'all'
            cur.execute("SELECT DISTINCT user_id FROM subscriptions WHERE alert_type = ? OR alert_type = 'all'", (target_location,))
        else:
            # send to all subscribers
            cur.execute("SELECT DISTINCT user_id FROM subscriptions")

        subs = [r[0] for r in cur.fetchall()]
        if not subs:
            logging.info("No subscribers matched for broadcast id=%s", bid)
            # still mark as sent to avoid retry loops (or you may choose to leave for manual retry)
            cur.execute("UPDATE broadcasts SET sent = 1, sent_at = ? WHERE id = ?", (datetime.utcnow(), bid))
            conn.commit()
            continue

        success_count = 0
        for user_id in subs:
            # user_id expected format: 'whatsapp:+9199...' OR '+9199...' (sms)
            ok = send_message(user_id, message)
            if ok:
                success_count += 1

        # mark broadcast as sent (you can change logic to partial success tracking)
        cur.execute("UPDATE broadcasts SET sent = 1, sent_at = ? WHERE id = ?", (datetime.utcnow(), bid))
        conn.commit()
        logging.info("Broadcast id=%s processed, attempted=%d, success_approx=%d", bid, len(subs), success_count)

    conn.close()

# Schedule every 60 seconds (adjust interval as needed)
@scheduler.scheduled_job('interval', seconds=60)
def tick():
    try:
        process_pending_broadcasts()
    except Exception:
        logging.exception("Error processing broadcasts")

if __name__ == "__main__":
    logging.info("Starting alert worker...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down worker.")
