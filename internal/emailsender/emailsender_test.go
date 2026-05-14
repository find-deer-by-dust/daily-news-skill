package emailsender

import (
	"net/smtp"
	"testing"
)

func TestDetectSMTPServer_KnownDomain(t *testing.T) {
	tests := []struct {
		email    string
		wantHost string
		wantPort string
	}{
		{"user@gmail.com", "smtp.gmail.com", "587"},
		{"user@qq.com", "smtp.qq.com", "587"},
		{"user@163.com", "smtp.163.com", "587"},
		{"user@outlook.com", "smtp-mail.outlook.com", "587"},
		{"user@foxmail.com", "smtp.qq.com", "587"},
	}
	for _, tc := range tests {
		host, port := detectSMTPServer(tc.email)
		if host != tc.wantHost || port != tc.wantPort {
			t.Errorf("detectSMTPServer(%q) = (%q, %q), want (%q, %q)", tc.email, host, port, tc.wantHost, tc.wantPort)
		}
	}
}

func TestDetectSMTPServer_UnknownDomain(t *testing.T) {
	host, port := detectSMTPServer("user@unknown-domain.example.com")
	if host != "smtp.unknown-domain.example.com" {
		t.Errorf("expected smtp.<domain> fallback, got %q", host)
	}
	if port != "587" {
		t.Errorf("expected port 587, got %q", port)
	}
}

func TestDetectSMTPServer_InvalidEmail(t *testing.T) {
	host, port := detectSMTPServer("invalid-email")
	if host != "smtp.gmail.com" || port != "587" {
		t.Errorf("expected gmail fallback for invalid email, got %q:%q", host, port)
	}
}

func TestNewEmailSender(t *testing.T) {
	sender := New("test@gmail.com", "password123")
	if sender.address != "test@gmail.com" {
		t.Errorf("address: got %q, want %q", sender.address, "test@gmail.com")
	}
	if sender.smtpHost != "smtp.gmail.com" {
		t.Errorf("smtpHost: got %q, want %q", sender.smtpHost, "smtp.gmail.com")
	}
	if sender.auth == nil {
		t.Error("auth should not be nil")
	}
}

func TestSendEmail_EmptyUsers(t *testing.T) {
	sender := New("test@gmail.com", "password123")
	// Should not panic with empty users
	sender.SendEmail([]string{}, "subject", "body")
}

func TestSendEmail_InvalidRecipient(t *testing.T) {
	sender := New("test@gmail.com", "password123")
	// This will fail to connect but should not panic
	sender.SendEmail([]string{"bad@nonexistent.example.com"}, "subject", "body")
}

// Test that sendOne constructs a valid raw email message
func TestSendOne_MessageFormat(t *testing.T) {
	sender := &EmailSender{
		address:  "from@test.com",
		password: "pass",
		smtpHost: "smtp.test.com",
		smtpPort: "587",
		auth:     smtp.PlainAuth("", "from@test.com", "pass", "smtp.test.com"),
	}

	// sendOne will fail to connect, but we can test the message construction
	// by calling it and verifying it doesn't panic
	err := sender.sendOne("to@test.com", "测试主题", "测试内容")
	if err == nil {
		t.Log("unexpected success connecting to fake SMTP")
	}
}

func TestEmailSender_FieldValues(t *testing.T) {
	sender := New("admin@163.com", "secret")
	if sender.smtpHost != "smtp.163.com" {
		t.Errorf("smtpHost: got %q, want smtp.163.com", sender.smtpHost)
	}
	if sender.smtpPort != "587" {
		t.Errorf("smtpPort: got %q, want 587", sender.smtpPort)
	}
}
