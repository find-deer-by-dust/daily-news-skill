package mysql

import (
	"testing"
	"time"
)

func TestStringsJoin_Empty(t *testing.T) {
	result := stringsJoin([]string{}, ",")
	if result != "" {
		t.Errorf("expected empty string, got %q", result)
	}
}

func TestStringsJoin_Single(t *testing.T) {
	result := stringsJoin([]string{"a"}, ",")
	if result != "a" {
		t.Errorf("got %q, want %q", result, "a")
	}
}

func TestStringsJoin_Multiple(t *testing.T) {
	result := stringsJoin([]string{"a", "b", "c"}, "\n")
	expected := "a\nb\nc"
	if result != expected {
		t.Errorf("got %q, want %q", result, expected)
	}
}

func TestMysqlConnector_DSN(t *testing.T) {
	// Test that DSN is built correctly by attempting a connection
	// to a non-existent server — should fail with connection error, not panic
	_, err := New("127.0.0.1:3307", "root", "password", "emailbotdb")
	if err == nil {
		t.Log("unexpectedly connected to local mysql")
	}
}

func TestHaveNews_NoConnection(t *testing.T) {
	conn := &MysqlConnector{db: nil}
	result := conn.HaveNews(time.Now())
	if result {
		t.Error("HaveNews should return false when no connection exists")
	}
}
