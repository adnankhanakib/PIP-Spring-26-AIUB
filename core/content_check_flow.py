import json
import os
import re

import questionary

from core.ContentCheck import ContentChecker
from core.EmailClient import EmailSender
from utils.inputs import ask_text, ask_email, ask_password, ask_autocomplete, ask_email_autocomplete

_HERE = os.path.dirname(os.path.abspath(__file__))
SMTP_JSON = os.path.join(_HERE, "..", "smtp.json")
TEMPLATES_DIR = os.path.join(_HERE, "..", "templates")


class _Cancelled(Exception):
    pass


def _require(value):
    if value is None:
        raise _Cancelled
    return value


def _load_smtp_configs():
    try:
        with open(SMTP_JSON, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save_smtp_config(config):
    configs = _load_smtp_configs()
    configs.append(config)
    with open(SMTP_JSON, "w") as f:
        json.dump(configs, f, indent=2)
    print(f"  Config '{config['name']}' saved.")


def _collect_custom_smtp():
    print("\n── Custom SMTP Details ──")
    host = _require(ask_text("SMTP host:", default="smtp.gmail.com"))
    port = int(_require(ask_text("SMTP port:", default="587")))
    tls_choice = _require(questionary.select(
        "Security:", choices=["STARTTLS (port 587)", "SSL/TLS (port 465)", "None"]
    ).ask())
    tls = tls_choice == "STARTTLS (port 587)"
    username = _require(ask_email("Username (email):"))
    password = _require(ask_password("Password / app password:"))
    from_name = ask_text("From name (display name):", default="", allow_empty=True) or None

    config = {"name": "Custom", "host": host, "port": port,
              "username": username, "password": password, "tls": tls,
              "from_name": from_name}

    save = questionary.confirm("Save this config for future use?", default=True).ask()
    if save is None:
        raise _Cancelled
    if save:
        config["name"] = _require(ask_text("Config name:"))
        _save_smtp_config(config)

    return config


def _pick_smtp_config():
    configs = _load_smtp_configs()
    labels = [f"{c['name']} ({c['host']}) [{c['username']}]" for c in configs]
    labels.append("Custom SMTP Details")

    choice = _require(questionary.select("Select SMTP connection:", choices=labels).ask())

    if choice == "Custom SMTP Details":
        return _collect_custom_smtp()

    idx = labels.index(choice)
    return configs[idx]


def _pick_html_body():
    templates = [
        f for f in os.listdir(TEMPLATES_DIR)
        if os.path.isfile(os.path.join(TEMPLATES_DIR, f))
    ]

    choices = []
    if templates:
        choices.extend(templates)
    else:
        print("  (Template folder is empty)")
    choices.append("Custom HTML")

    selection = _require(questionary.select("HTML source:", choices=choices).ask())

    if selection == "Custom HTML":
        return _require(ask_text("Enter HTML body:"))

    with open(os.path.join(TEMPLATES_DIR, selection), "r", encoding="utf-8") as f:
        return f.read()


def _render_score_bar(score: float) -> str:
    filled = min(int(score), 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {score:.1f}"


def content_check_flow():
    print("\n-- Content Testing ──")
    print("  This tool sends your email to a temporary inbox and")
    print("  analyses it for spam score using SpamAssassin rules.\n")

    try:
        checker = ContentChecker()

        temp_address = checker.generate_email()
        print(f"  Temporary inbox : {temp_address}")

        config = _pick_smtp_config()

        smtp_server = config["host"]
        port = config["port"]
        use_tls = config.get("tls", True)
        username = config["username"]
        password = config["password"]
        from_name = config.get("from_name") or None

        sender = _require(ask_email_autocomplete(
            "From address:",
            choices=[username],
            default=username
        ))

        subject = _require(ask_autocomplete("Subject:", choices=[]))

        use_html = _require(questionary.confirm("Send as HTML?", default=True).ask())
        if use_html:
            html = _pick_html_body()
            body = None
        else:
            body = _require(ask_text("Plain-text body:"))
            html = None

        print(f"\n  Sending test email to {temp_address} ...")
        client = EmailSender(smtp_server, port, username, password,
                             use_tls=use_tls, from_name=from_name)
        ok = client.send_email(
            sender, [temp_address], subject,
            body=body, html=html
        )

        if not ok:
            print("  ❌ Failed to send the test email. Check your SMTP settings.")
            questionary.press_any_key_to_continue().ask()
            return

        print("  ✅ Test email sent. Waiting for delivery...")

        timeout = 120
        received = checker.wait_for_message(timeout=timeout)
        print()

        if not received:
            print(f"  ⚠️  No message received within {timeout} seconds.")
            print("     The email may still be in transit. Try again later.")
            questionary.press_any_key_to_continue().ask()
            return

        print("  📬 Message received! Analysing content...\n")

        result = checker.check_received_email()
        if result is None:
            print("  Could not read the received message.")
            questionary.press_any_key_to_continue().ask()
            return

        score = result["score"]
        report = result["report"]

        print("─" * 50)
        print("  SPAM SCORE REPORT")
        print("─" * 50)
        print(f"  Score  : {_render_score_bar(score)}")

        if score < 2:
            verdict = "✅ Excellent — very unlikely to be flagged as spam."
        elif score < 5:
            verdict = "⚠️  Moderate — may be filtered by strict spam rules."
        else:
            verdict = "❌ High risk — likely to land in spam folders."

        print(f"  Verdict: {verdict}")
        print()
        print("  Detailed Report:")
        print("─" * 50)
        if report:
            for line in report.strip().splitlines():
                print(f"  {line}")
        else:
            print("  (No detailed report available)")
        print("─" * 50)

        questionary.press_any_key_to_continue().ask()

    except _Cancelled:
        print("Cancelled.")
