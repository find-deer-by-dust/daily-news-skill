from email.message import EmailMessage
from email.utils import formatdate
import hashlib
import logging
import smtplib
import ssl

from .email_html import render_report_html

log = logging.getLogger(__name__)


class Delivery:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def send(self, day, report, *, resend=False):
        failures = []
        accepted_count = skipped_count = 0
        html_report = None
        for recipient in self.settings.recipients:
            previous = self.store.delivery(day, recipient)
            if previous and previous['status'] in {'sending', 'unknown'}:
                failures.append(recipient + ': 上次投递结果不确定，请先人工核对并 resolve-delivery')
                continue
            if previous and previous['status'] == 'sent' and not resend:
                log.info('已发送，跳过收件人：%s', recipient)
                skipped_count += 1
                continue
            if html_report is None:
                html_report = render_report_html(report, title=f'每日早报 {day}')
            digest = hashlib.sha256((day + recipient + report).encode()).hexdigest()[:32]
            message_id = previous['message_id'] if previous else f'<daily-news.{digest}@{self.settings.email_address.split("@")[-1]}>'
            msg = EmailMessage()
            msg['From'] = self.settings.email_address
            msg['To'] = recipient
            msg['Subject'] = f'每日早报 {day}'
            msg['Date'] = formatdate(localtime=False)
            msg['Message-ID'] = message_id
            msg.set_content(report, charset='utf-8')
            msg.add_alternative(html_report, subtype='html', charset='utf-8')
            self.store.begin_delivery(day, recipient, message_id)
            server = None
            submitted = False
            try:
                context = ssl.create_default_context()
                if self.settings.smtp_security == 'ssl':
                    server = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port,
                                             timeout=self.settings.timeout, context=context)
                else:
                    server = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port,
                                          timeout=self.settings.timeout)
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(self.settings.email_address, self.settings.email_password)
                submitted = True
                refused = server.send_message(msg, from_addr=self.settings.email_address, to_addrs=[recipient])
                if refused:
                    raise smtplib.SMTPRecipientsRefused(refused)
                # Commit acceptance before QUIT. A QUIT disconnect does not undo delivery.
                self.store.finish_delivery(day, recipient, 'sent')
                accepted_count += 1
                log.info('SMTP 已接受邮件：%s', recipient)
            except Exception as exc:
                explicit_rejection = isinstance(exc, (smtplib.SMTPRecipientsRefused,
                    smtplib.SMTPSenderRefused, smtplib.SMTPDataError))
                status = 'unknown' if submitted and not explicit_rejection else 'failed'
                detail = type(exc).__name__  # No server response bodies or credentials in logs.
                self.store.finish_delivery(day, recipient, status, detail)
                failures.append(f'{recipient}: {status} ({detail})')
            finally:
                if server:
                    try: server.quit()
                    except Exception: server.close()
        if failures:
            raise RuntimeError('邮件未全部确认成功：' + '; '.join(failures))
        return {'accepted_count': accepted_count, 'skipped_count': skipped_count,
                'email_submitted': accepted_count > 0}
