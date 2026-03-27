import csv
import json
import os
import re
import time
from datetime import date

import questionary

from core.EmailClient import EmailSender
from core.Memory import Memory
from utils.inputs import ask_text, ask_email, ask_password, ask_autocomplete, ask_email_autocomplete

mem = Memory()


class _Cancelled(Exception):
    pass


def _require(value):
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
    print("\n-- Custom SMTP Details --")
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


def _resolve_placeholders(content: str, context: dict) -> str:
    found = list(dict.fromkeys(re.findall(r'\{\{(\w+)\}\}', content)))
    if not found:
        return content

    values = dict(context)
    unknown = [name for name in found if name not in values]

    if unknown:
        print("\n-- Template Placeholders --")
        for name in unknown:
            values[name] = _require(ask_text(f"Value for {{{{{name}}}}}:"))

    for name, value in values.items():
        content = content.replace(f'{{{{{name}}}}}', value)

    return content


def _resolve_placeholders_per_row(content: str, global_values: dict, row_context: dict) -> str:
    found = list(dict.fromkeys(re.findall(r'\{\{(\w+)\}\}', content)))
    if not found:
        return content

    values = {**global_values, **row_context}

    for name, value in values.items():
        content = content.replace(f'{{{{{name}}}}}', value)

    return content


def _collect_attachments() -> list:
    attachments = []
    while True:
        add = questionary.confirm(
            f"Add {'an' if not attachments else 'another'} attachment?",
            default=False
        ).ask()
        if not add:
            break
        path = ask_text("File path:", allow_empty=True)
        if not path:
            continue
        path = path.strip('"').strip("'")
        if not os.path.isfile(path):
            print(f"  File not found: {path}")
            continue
        attachments.append(path)
        print(f"  Added: {os.path.basename(path)}")
    return attachments


def _load_recipients_from_csv(path: str) -> list[dict]:
    recipients = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            if "email" not in row or not row["email"]:
                continue
            recipients.append(row)
    return recipients


def _load_recipients_manual() -> list[dict]:
    print("\n  Type each recipient as:  email, Name")
    print("  Leave blank and press Enter when you're done.\n")
    recipients = []
    while True:
        entry = ask_text(f"Recipient {len(recipients) + 1}:", allow_empty=True)
        if not entry:
            if not recipients:
                print("  You need at least one recipient!")
                continue
            break
        parts = [p.strip() for p in entry.split(",", 1)]
        email = parts[0]
        name = parts[1] if len(parts) > 1 else email.split("@")[0]
        recipients.append({"email": email, "name": name})
        print(f"  Added: {name} <{email}>")
    return recipients


def _pick_recipients() -> list[dict]:
    source = _require(questionary.select(
        "Where are your recipients?",
        choices=[
            "Load from CSV file",
            "Enter manually",
        ]
    ).ask())

    if source == "Load from CSV file":
        while True:
            path = _require(ask_text("CSV file path:"))
            path = path.strip('"').strip("'")
            if not os.path.isfile(path):
                print(f"  File not found: {path}")
                continue
            try:
                recipients = _load_recipients_from_csv(path)
                if not recipients:
                    print("  No valid rows found. Make sure your CSV has an 'email' column.")
                    continue
                print(f"  Loaded {len(recipients)} recipient(s) from CSV.")
                return recipients
            except Exception as e:
                print(f"  Could not read CSV: {e}")

    return _load_recipients_manual()


def _preview_recipients(recipients: list[dict]):
    print(f"\n-- Recipients Preview ({len(recipients)} total) --")
    show = recipients[:5]
    for r in show:
        name = r.get("name", r["email"].split("@")[0])
        print(f"  • {name} <{r['email']}>")
    if len(recipients) > 5:
        print(f"  ... and {len(recipients) - 5} more")


def _collect_global_placeholders(template: str, auto_keys: set) -> dict:
    found = list(dict.fromkeys(re.findall(r'\{\{(\w+)\}\}', template)))
    row_keys = {"email", "name", "to_name", "to_mail"}
    global_unknowns = [
        f for f in found
        if f not in auto_keys and f not in row_keys
    ]

    if not global_unknowns:
        return {}

    print("\n-- Global Placeholders (same value for everyone) --")
    values = {}
    for name in global_unknowns:
        values[name] = _require(ask_text(f"Value for {{{{{name}}}}}:"))

    return values


def send_bulk_email_flow():
    print("\n-- Send Bulk Emails --")

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

        subject = _require(ask_autocomplete("Subject:", choices=mem.get("subjects") or []))

        use_html = _require(questionary.confirm("Send as HTML?", default=False).ask())
        if use_html:
            raw_html = _pick_html_body()
            raw_body = None
        else:
            raw_body = _require(ask_text("Plain-text body:"))
            raw_html = None

        recipients = _pick_recipients()
        _preview_recipients(recipients)

        auto_keys = {"from_mail", "to_mail", "to_name", "today_date"}
        template_content = raw_html if raw_html is not None else (raw_body or "")
        full_template = template_content + " " + subject
        global_values = _collect_global_placeholders(full_template, auto_keys)

        attachments = _collect_attachments()

        delay_input = ask_text("Delay between emails in seconds (0 for no delay):", default="1", allow_empty=True)
        delay = float(delay_input) if delay_input else 1.0

        print(f"\n-- Bulk Send Summary --")
        from_display = f"{from_name} <{sender}>" if from_name else sender
        print(f"  From        : {from_display}")
        print(f"  Subject     : {subject}")
        print(f"  Recipients  : {len(recipients)}")
        print(f"  Format      : {'HTML' if use_html else 'Plain Text'}")
        if attachments:
            print(f"  Attachments : {len(attachments)} file(s)")
        print(f"  Delay       : {delay}s between emails")

        if not _require(questionary.confirm("Start sending to all recipients?", default=True).ask()):
            print("Cancelled.")
            questionary.press_any_key_to_continue().ask()
            return

        client = EmailSender(smtp_server, port, username, password, use_tls=use_tls, from_name=from_name)

        sent = 0
        failed = 0
        failed_list = []

        print()
        for i, row in enumerate(recipients, start=1):
            to_email = row["email"]
            to_name = row.get("name") or to_email.split("@")[0]

            row_ctx = {
                "from_mail":  sender,
                "to_mail":    to_email,
                "to_name":    to_name,
                "today_date": date.today().strftime("%B %d, %Y"),
                **{k: v for k, v in row.items() if k not in ("email",)},
                **global_values,
            }

            final_subject = _resolve_placeholders_per_row(subject, global_values, row_ctx)

            final_html = None
            final_body = None

            if raw_html is not None:
                final_html = _resolve_placeholders_per_row(raw_html, global_values, row_ctx)
            if raw_body is not None:
                final_body = _resolve_placeholders_per_row(raw_body, global_values, row_ctx)

            ok = client.send_email(
                sender,
                [to_email],
                final_subject,
                body=final_body,
                html=final_html,
                attachments=attachments or None
            )

            status = "✅" if ok else "❌"
            print(f"  [{i}/{len(recipients)}] {status}  {to_name} <{to_email}>")

            if ok:
                sent += 1
                mem.add_to("sendTo", to_email)
            else:
                failed += 1
                failed_list.append(f"{to_name} <{to_email}>")

            if delay > 0 and i < len(recipients):
                time.sleep(delay)

        mem.add_to("usernames", sender)
        mem.add_to("subjects", subject)

        print(f"\n-- Done! --")
        print(f"  Sent    : {sent}")
        print(f"  Failed  : {failed}")

        if failed_list:
            print("\n  Failed recipients:")
            for entry in failed_list:
                print(f"    • {entry}")

        questionary.press_any_key_to_continue().ask()

    except _Cancelled:
        print("Cancelled.")
