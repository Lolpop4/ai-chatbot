import sqlite3, os
from rasa_sdk import Action

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "healthbot.db")

class ActionReportOutbreak(Action):
    def name(self):
        return "action_report_outbreak"

    def run(self, dispatcher, tracker, domain):
        disease = next(tracker.get_latest_entity_values("disease"), None)
        location = next(tracker.get_latest_entity_values("location"), None)
        reporter = tracker.sender_id

        if not (disease and location):
            dispatcher.utter_message("⚠️ Please provide both disease and location.")
            return []

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO alerts_log (district, disease, cases, date) VALUES (?, ?, ?, DATE('now'))",
            (location, disease, 1)
        )
        conn.commit()
        conn.close()

        dispatcher.utter_message(f"✅ Outbreak of {disease} in {location} recorded.")
        return []

class ActionSaveMessage(Action):
    def name(self):
        return "action_save_message"

    def run(self, dispatcher, tracker, domain):
        user = tracker.sender_id
        message = tracker.latest_message.get("text")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user, message) VALUES (?, ?)", (user, message))
        conn.commit()
        conn.close()

        return []
