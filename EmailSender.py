import zmail
import logging
from config import Config

logger = logging.getLogger(__name__)

class EmailSender:
    
    def __init__(self):
        self.server = zmail.server(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
        
    def sendEmail(self, users, subject, content_text):
        if not users:
            logger.warning("No users to send email to.")
            return

        if not isinstance(users, list):
            users = [users]

        logger.info(f"Sending email '{subject}' to {len(users)} recipients.")
        
        for user in users:
            try:
                self.server.send_mail(user, {'subject': subject, 'content_text': content_text})
                logger.info(f"Email sent successfully to {user}")
            except Exception as e:
                logger.error(f"Failed to send email to {user}: {e}")
