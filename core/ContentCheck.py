import os
import random
import string
import time

import requests
import spamcheck

_FALLBACK_DOMAINS = (
    "1secmail.com",
    "1secmail.net",
    "1secmail.org",
    "esiix.com",
    "wwjmp.com",
    "xojxe.com",
    "yoggm.com",
)

_API = "https://www.1secmail.com/api/v1/"


def _get_domains() -> tuple:
    try:
        resp = requests.get(_API, params={"action": "getDomainList"}, timeout=10)
        resp.raise_for_status()
        return tuple(resp.json())
    except Exception:
        return _FALLBACK_DOMAINS


def _random_username(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class ContentChecker:

    def __init__(self):
        self._username: str | None = None
        self._domain: str | None = None
        self._session = requests.Session()

    @property
    def address(self) -> str | None:
        if self._username and self._domain:
            return f"{self._username}@{self._domain}"
        return None

    def generate_email(self) -> str:
        domains = _get_domains()
        self._username = _random_username()
        self._domain = random.choice(domains)
        return self.address

    def _get_inbox(self) -> list:
        resp = self._session.get(
            _API,
            params={"action": "getMessages", "login": self._username, "domain": self._domain},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def _get_message(self, msg_id: int) -> dict:
        resp = self._session.get(
            _API,
            params={
                "action": "readMessage",
                "login": self._username,
                "domain": self._domain,
                "id": msg_id,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def wait_for_message(self, timeout: int = 120, poll_interval: int = 3) -> bool:
        if not self.address:
            raise RuntimeError("Call generate_email() first.")

        elapsed = 0
        while elapsed < timeout:
            try:
                messages = self._get_inbox()
                if messages:
                    return True
            except Exception:
                pass
            print(f"  Waiting for email... ({elapsed}s / {timeout}s)", end="\r")
            time.sleep(poll_interval)
            elapsed += poll_interval

        print()
        return False

    def get_score_and_report(self, html_content: str) -> dict:
        tmp_path = "_content_check_tmp.html"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            result = spamcheck.check(tmp_path, report=True)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return {
            "score": result.get("score", 0),
            "report": result.get("report", ""),
        }

    def check_received_email(self) -> dict | None:
        try:
            inbox = self._get_inbox()
            if not inbox:
                return None
            msg = self._get_message(inbox[0]["id"])
        except Exception:
            return None

        html_content = msg.get("htmlBody") or f"<html><body>{msg.get('textBody', '')}</body></html>"
        return self.get_score_and_report(html_content)
