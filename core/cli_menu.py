import questionary
from core.send_single import send_single_email_flow

def main_menu():
    choices = [
        "Send a Single Email",
        "Send Bulk Emails",
        "View Logs",
        "Content Testing",
        "Exit"
    ]
    return questionary.select(
        "Welcome to SuperMailer, please select an action:",
        choices=choices,
        qmark="🔹",
        pointer=">>"
    ).ask()


def cli():
    while True:
        action = main_menu()

        if action == "Send a Single Email":
            send_single_email_flow()

        elif action == "Exit" or action is None:
            print("Goodbye!")
            break

        else:
            print(f"'{action}' is not implemented yet.")
            questionary.press_any_key_to_continue().ask()
