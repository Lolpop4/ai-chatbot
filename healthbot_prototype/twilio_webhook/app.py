# healthbot/twilio_webhook/app.py
from flask import Flask, request, Response
import requests, os, sqlite3
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)
RASA_URL = os.getenv("RASA_URL", "http://localhost:5005/webhooks/rest/webhook")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "healthbot.db")

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")  # e.g. 'whatsapp:+9199...' or '+9199...'

    # log message locally
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user, message) VALUES (?, ?)", (sender, incoming_msg))
        conn.commit()
        conn.close()
    except Exception:
        # don't fail on logging error
        app.logger.exception("Failed to log incoming message")

    # send to Rasa
    try:
        rasa_response = requests.post(RASA_URL, json={"sender": sender, "message": incoming_msg}, timeout=10)
        rasa_replies = rasa_response.json()
    except Exception:
        rasa_replies = []

    reply_text = ""
    for r in rasa_replies:
        if "text" in r:
            reply_text += r["text"] + "\n"

    if not reply_text.strip():
        reply_text = "🤖 Sorry, I didn't understand that."

    twilio_resp = MessagingResponse()
    twilio_resp.message(reply_text.strip())
    return Response(str(twilio_resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
