import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
import os
from typing import List, Optional


class EmailSender:
    def __init__(self, smtp_server: str, port: int, username: str, password: str, use_tls: bool = True, from_name: str = None):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_name = from_name

    def _create_message(self, sender: str, recipients: List[str], subject: str,
                        body: str = None, html: str = None,
                        attachments: Optional[List[str]] = None) -> MIMEMultipart:
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((self.from_name, sender)) if self.from_name else sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject

        if body:
            msg.attach(MIMEText(body, 'plain'))
        if html:
            msg.attach(MIMEText(html, 'html'))

        # Attach files
        if attachments:
            for file_path in attachments:
                self._attach_file(msg, file_path)

        return msg

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        try:
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)

                filename = os.path.basename(file_path)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(part)
        except Exception as e:
            print(f"Error attaching file {file_path}: {e}")

    def send_email(self, sender: str, recipients: List[str], subject: str,
                   body: str = None, html: str = None,
                   attachments: Optional[List[str]] = None) -> bool:
        msg = self._create_message(sender, recipients, subject, body, html, attachments)

        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.port)
                server.starttls(context=ssl.create_default_context())
            else:
                server = smtplib.SMTP_SSL(self.smtp_server, self.port, context=ssl.create_default_context())

            server.login(self.username, self.password)
            server.sendmail(sender, recipients, msg.as_string())
            server.quit()
            print("Email sent successfully!")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False