import json
import os
import questionary
from core.EmailClient import EmailSender
from core.Memory import Memory
from utils.inputs import ask_text, ask_email, ask_password, ask_email_autocomplete, ask_autocomplete

mem = Memory()


class _Cancelled(Exception):
    pass


def _require(value):
    """Raise _Cancelled if a questionary prompt returned None (Ctrl+C / Escape)."""
    if value is None:
        raise _Cancelled
    return value


_HERE = os.path.dirname(os.path.abspath(__file__))
SMTP_JSON = os.path.join(_HERE, "..", "smtp.json")
TEMPLATES_DIR = os.path.join(_HERE, "..", "templates")


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
    print(f"  Config '{config['name']}' saved to smtp.json.")


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


def send_single_email_flow():
    print("\n── Send Single Email ──")

    try:
        config = _pick_smtp_config()

        smtp_server = config["host"]
        port = config["port"]
        use_tls = config.get("tls", True)
        username = config["username"]
        password = config["password"]
        from_name = config.get("from_name") or None

        usernames = mem.get("usernames") or []
        if username not in usernames:
            usernames = [username] + usernames
        sender = _require(ask_email_autocomplete("From address:", choices=usernames, default=username))

        to = _require(ask_email_autocomplete("To address:", choices=mem.get("sendTo") or []))
        subject = _require(ask_autocomplete("Subject:", choices=mem.get("subjects") or []))

        use_html = _require(questionary.confirm("Send as HTML?", default=False).ask())
        if use_html:
            html = _pick_html_body()
            body = None
        else:
            body = _require(ask_text("Plain-text body:"))
            html = None

        print(f"\n  Config : {config['name']} ({smtp_server})")
        from_display = f"{from_name} <{sender}>" if from_name else sender
        print(f"  From   : {from_display}")
        print(f"  To     : {to}")
        print(f"  Subject: {subject}")
        if not _require(questionary.confirm("Send this email?", default=True).ask()):
            print("Cancelled.")
            questionary.press_any_key_to_continue().ask()
            return

        client = EmailSender(smtp_server, port, username, password, use_tls=use_tls, from_name=from_name)
        ok = client.send_email(sender, [to], subject, body=body, html=html)

        if ok:
            mem.add_to("usernames", sender)
            mem.add_to("sendTo", to)
            mem.add_to("subjects", subject)
            print("✅ Email sent successfully!")
        else:
            print("❌ Failed to send email.")
        questionary.press_any_key_to_continue().ask()

    except _Cancelled:
        print("Cancelled.")
