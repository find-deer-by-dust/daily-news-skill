package emailsender

import (
	"fmt"
	"log/slog"
	"net/smtp"
	"strings"
)

var smtpHosts = map[string]string{
	"gmail.com":     "smtp.gmail.com",
	"qq.com":        "smtp.qq.com",
	"163.com":       "smtp.163.com",
	"126.com":       "smtp.126.com",
	"outlook.com":   "smtp-mail.outlook.com",
	"hotmail.com":   "smtp-mail.outlook.com",
	"live.com":      "smtp-mail.outlook.com",
	"foxmail.com":   "smtp.qq.com",
	"sina.com":      "smtp.sina.com",
	"sohu.com":      "smtp.sohu.com",
	"aliyun.com":    "smtp.aliyun.com",
	"icloud.com":    "smtp.mail.me.com",
	"yahoo.com":     "smtp.mail.yahoo.com",
	"yeah.net":      "smtp.yeah.net",
}

type EmailSender struct {
	address  string
	password string
	smtpHost string
	smtpPort string
	auth     smtp.Auth
}

func New(address, password string) *EmailSender {
	host, port := detectSMTPServer(address)
	auth := smtp.PlainAuth("", address, password, host)
	return &EmailSender{
		address:  address,
		password: password,
		smtpHost: host,
		smtpPort: port,
		auth:     auth,
	}
}

func detectSMTPServer(email string) (host, port string) {
	parts := strings.SplitN(email, "@", 2)
	if len(parts) != 2 {
		return "smtp.gmail.com", "587"
	}
	domain := parts[1]

	if h, ok := smtpHosts[domain]; ok {
		return h, "587"
	}

	return "smtp." + domain, "587"
}

func (e *EmailSender) SendEmail(users []string, subject, contentText string) {
	if len(users) == 0 {
		slog.Warn("没有需要发送邮件的用户")
		return
	}

	slog.Info("正在发送邮件", "recipientCount", len(users), "subject", subject)

	successCount := 0
	for _, user := range users {
		if err := e.sendOne(user, subject, contentText); err != nil {
			slog.Error("无法发送邮件", "recipient", user, "error", err)
		} else {
			slog.Info("成功将邮件发送至", "recipient", user)
			successCount++
		}
	}

	slog.Info("邮件发送完成", "successCount", successCount, "totalCount", len(users))
}

func (e *EmailSender) sendOne(to, subject, body string) error {
	msg := fmt.Sprintf(
		"From: %s\r\nTo: %s\r\nSubject: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=\"UTF-8\"\r\n\r\n%s",
		e.address, to, subject, body,
	)

	addr := fmt.Sprintf("%s:%s", e.smtpHost, e.smtpPort)
	return smtp.SendMail(addr, e.auth, e.address, []string{to}, []byte(msg))
}
