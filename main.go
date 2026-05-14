package main

import (
	"log/slog"
	"os"

	"emailBot/config"
	"emailBot/internal/service"
)

func main() {
	config.InitLogger()

	if err := config.Load(); err != nil {
		slog.Error("配置加载失败", "error", err)
		os.Exit(1)
	}

	if err := config.AppConfig.Validate(); err != nil {
		slog.Error(err.Error())
		os.Exit(1)
	}

	slog.Info("正在启动 EmailBot 应用程序...")

	defer func() {
		if r := recover(); r != nil {
			slog.Error("主程序发生未处理的异常", "panic", r)
		}
	}()

	svc := service.New(7)
	svc.RunDailyTask()
}
