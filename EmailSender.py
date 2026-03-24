import zmail
import logging
from typing import List, Union
from config import Config

logger = logging.getLogger(__name__)

class EmailSender:

    def __init__(self):
        self.server = zmail.server(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)

    def sendEmail(self, users: Union[str, List[str]], subject: str, content_text: str) -> None:
        """
        向指定的一个或多个用户发送邮件。
        """
        if not users:
            logger.warning("没有需要发送邮件的用户。")
            return

        if not isinstance(users, list):
            users = [users]

        logger.info(f"正在向 {len(users)} 位收件人发送邮件 '{subject}'。")

        success_count = 0
        for user in users:
            try:
                # 遍历发送邮件，当某个特定邮箱地址发送失败时
                # 可以保证不会阻塞后续其他用户的邮件发送。
                self.server.send_mail(user, {'subject': subject, 'content_text': content_text})
                logger.info(f"成功将邮件发送至 {user}")
                success_count += 1
            except Exception as e:
                logger.error(f"无法发送邮件至 {user}: {e}")

        logger.info(f"邮件发送完成。成功数量: {success_count}/{len(users)}")
