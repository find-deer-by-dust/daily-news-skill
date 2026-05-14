package config

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"

	"github.com/joho/godotenv"
	"gopkg.in/natefinch/lumberjack.v2"
)

type Config struct {
	DBHost     string
	DBUser     string
	DBPassword string
	DBName     string

	AIAPIKey  string
	AIBaseURL string
	AIModel   string

	EmailAddress  string
	EmailPassword string

	NewsAPIKey string
	NewsAPIURL string

	Users []string
}

var AppConfig *Config

func Load() error {
	_ = godotenv.Load()

	AppConfig = &Config{
		DBHost:     getEnv("DB_HOST", "nas"),
		DBUser:     getEnv("DB_USER", "root"),
		DBPassword: os.Getenv("DB_PASSWORD"),
		DBName:     os.Getenv("DB_NAME"),

		AIAPIKey:  os.Getenv("AI_API_KEY"),
		AIBaseURL: os.Getenv("AI_BASE_URL"),
		AIModel:   getEnv("AI_MODEL", "gpt-3.5-turbo"),

		EmailAddress:  os.Getenv("EMAIL_ADDRESS"),
		EmailPassword: os.Getenv("EMAIL_PASSWORD"),

		NewsAPIKey: os.Getenv("NEWS_API_KEY"),
		NewsAPIURL: getEnv("NEWS_API_URL", "https://v3.alapi.cn/api/zaobao"),

		Users: parseUsers(os.Getenv("USERS")),
	}
	return nil
}

func (c *Config) Validate() error {
	missing := []string{}
	if c.DBPassword == "" {
		missing = append(missing, "DB_PASSWORD")
	}
	if c.DBName == "" {
		missing = append(missing, "DB_NAME")
	}
	if c.AIAPIKey == "" {
		missing = append(missing, "AI_API_KEY")
	}
	if c.EmailAddress == "" {
		missing = append(missing, "EMAIL_ADDRESS")
	}
	if c.EmailPassword == "" {
		missing = append(missing, "EMAIL_PASSWORD")
	}
	if c.NewsAPIKey == "" {
		missing = append(missing, "NEWS_API_KEY")
	}
	if len(missing) > 0 {
		return fmt.Errorf("缺少必需的环境变量: %v", missing)
	}
	return nil
}

func InitLogger() {
	writer := io.MultiWriter(
		os.Stdout,
		&lumberjack.Logger{
			Filename:   "app.log",
			MaxAge:     7,
			LocalTime:  true,
		},
	)
	handler := slog.NewTextHandler(writer, &slog.HandlerOptions{Level: slog.LevelInfo})
	slog.SetDefault(slog.New(handler))
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func parseUsers(raw string) []string {
	if raw == "" {
		raw = "[]"
	}
	var users []string
	if err := json.Unmarshal([]byte(raw), &users); err != nil {
		return []string{}
	}
	return users
}
