package config

import (
	"os"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	os.Unsetenv("DB_HOST")
	os.Unsetenv("DB_USER")
	os.Unsetenv("AI_MODEL")
	os.Unsetenv("NEWS_API_URL")
	os.Unsetenv("USERS")

	if err := Load(); err != nil {
		t.Fatalf("Load() failed: %v", err)
	}

	if AppConfig.DBHost != "nas" {
		t.Errorf("DBHost default: got %q, want %q", AppConfig.DBHost, "nas")
	}
	if AppConfig.DBUser != "root" {
		t.Errorf("DBUser default: got %q, want %q", AppConfig.DBUser, "root")
	}
	if AppConfig.AIModel != "gpt-3.5-turbo" {
		t.Errorf("AIModel default: got %q, want %q", AppConfig.AIModel, "gpt-3.5-turbo")
	}
	if AppConfig.NewsAPIURL != "https://v3.alapi.cn/api/zaobao" {
		t.Errorf("NewsAPIURL default: got %q, want %q", AppConfig.NewsAPIURL, "https://v3.alapi.cn/api/zaobao")
	}
	if len(AppConfig.Users) != 0 {
		t.Errorf("Users default: got %v, want empty slice", AppConfig.Users)
	}
}

func TestLoadCustomValues(t *testing.T) {
	os.Setenv("DB_HOST", "custom-host")
	os.Setenv("DB_USER", "admin")
	os.Setenv("AI_MODEL", "gpt-4")
	os.Setenv("NEWS_API_URL", "https://custom.api.com/news")
	os.Setenv("USERS", `["a@b.com","c@d.com"]`)
	defer os.Unsetenv("DB_HOST")
	defer os.Unsetenv("DB_USER")
	defer os.Unsetenv("AI_MODEL")
	defer os.Unsetenv("NEWS_API_URL")
	defer os.Unsetenv("USERS")

	if err := Load(); err != nil {
		t.Fatalf("Load() failed: %v", err)
	}

	if AppConfig.DBHost != "custom-host" {
		t.Errorf("DBHost: got %q, want %q", AppConfig.DBHost, "custom-host")
	}
	if AppConfig.AIModel != "gpt-4" {
		t.Errorf("AIModel: got %q, want %q", AppConfig.AIModel, "gpt-4")
	}
	if len(AppConfig.Users) != 2 || AppConfig.Users[0] != "a@b.com" {
		t.Errorf("Users: got %v, want [a@b.com c@d.com]", AppConfig.Users)
	}
}

func TestValidateMissingRequired(t *testing.T) {
	Load()
	cfg := &Config{
		DBPassword:    "",
		DBName:        "",
		AIAPIKey:      "key",
		EmailAddress:  "a@b.com",
		EmailPassword: "pass",
		NewsAPIKey:    "token",
	}
	err := cfg.Validate()
	if err == nil {
		t.Fatal("expected error for missing fields")
	}
	msg := err.Error()
	if !contains(msg, "DB_PASSWORD") || !contains(msg, "DB_NAME") {
		t.Errorf("error should mention missing fields, got: %s", msg)
	}
}

func TestValidateAllPresent(t *testing.T) {
	cfg := &Config{
		DBPassword:    "p",
		DBName:        "n",
		AIAPIKey:      "k",
		EmailAddress:  "e",
		EmailPassword: "p",
		NewsAPIKey:    "k",
	}
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected no error, got: %v", err)
	}
}

func TestParseUsersInvalidJSON(t *testing.T) {
	users := parseUsers("not-json")
	if len(users) != 0 {
		t.Errorf("expected empty slice for invalid JSON, got %v", users)
	}
}

func TestParseUsersEmpty(t *testing.T) {
	users := parseUsers("")
	if len(users) != 0 {
		t.Errorf("expected empty slice, got %v", users)
	}
}

func contains(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
