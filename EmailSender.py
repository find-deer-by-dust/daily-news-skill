import zmail
import os
from dotenv import load_dotenv

load_dotenv(override=True)

class EmailSender:
    
    def __init__(self):
        self.emailKey = os.getenv('emailKey')
        self.server = zmail.server(os.getenv('email'), self.emailKey)
        
    def sendEmail(self, users, subject, content_text):
        print(users)
        for user in users:
            self.server.send_mail(user, {'subject': subject,'content_text': content_text})
            print("have sent email to " + user)