package service

import (
	"fmt"
	"log/slog"
	"time"

	"emailBot/config"
	"emailBot/internal/aibot"
	"emailBot/internal/emailsender"
	"emailBot/internal/mysql"
	"emailBot/internal/newsgetter"
)

type NewsService struct {
	coverageDays int
	newsGetter   *newsgetter.NewsGetter
	aiBot        *aibot.AiBot
	emailSender  *emailsender.EmailSender
}

func New(coverageDays int) *NewsService {
	cfg := config.AppConfig
	return &NewsService{
		coverageDays: coverageDays,
		newsGetter:   newsgetter.New(cfg.NewsAPIURL, cfg.NewsAPIKey),
		aiBot:        aibot.New(cfg.AIAPIKey, cfg.AIBaseURL, cfg.AIModel),
		emailSender:  emailsender.New(cfg.EmailAddress, cfg.EmailPassword),
	}
}

func (s *NewsService) buildPrompt(todayDate, newsContent, nearestNews string) string {
	history := nearestNews
	if history == "" {
		history = "无历史数据"
	}
	return fmt.Sprintf(
		"请对以下新闻内容进行专业点评。\n\n"+
			"【今日日期】\n%s\n\n"+
			"【今日新闻】\n%s\n\n"+
			"【历史参考（前几日新闻）】\n%s\n\n"+
			"【点评要求】\n"+
			"1. 对今日新闻做总体概述和点评，不需要逐条分析\n"+
			"2. 用通俗易懂的语言，减少专业性描述\n"+
			"3. 结合历史新闻，对未来方向做出预测\n"+
			"4. 纯文本输出，做好分段，不用 markdown 格式",
		todayDate, newsContent, history,
	)
}

func (s *NewsService) RunDailyTask() {
	today := time.Now()
	todayDate := today.Format("2006-01-02")

	if today.Hour() < 9 {
		slog.Info("获取新闻的时间太早（早于上午 9 点）。跳过执行。")
		return
	}

	cfg := config.AppConfig
	db, err := mysql.New(cfg.DBHost, cfg.DBUser, cfg.DBPassword, cfg.DBName)
	if err != nil {
		slog.Error("数据库连接失败", "error", err)
		return
	}
	defer db.Close()

	if db.HaveNews(today) {
		slog.Info(fmt.Sprintf("%s 的新闻已经存在。跳过执行。", todayDate))
		return
	}

	slog.Info(fmt.Sprintf("未找到 %s 的新闻。开始获取流程。", todayDate))

	newsContent := s.newsGetter.GetDailyNews()
	if newsContent == "" {
		slog.Error("获取新闻内容失败。中止每日任务。")
		return
	}

	nearestNews := db.GetNearestNews(s.coverageDays - 1)

	prompt := s.buildPrompt(todayDate, newsContent, nearestNews)
	aiReply := s.aiBot.Chat(prompt)

	if err := db.Insert(today, newsContent, aiReply); err != nil {
		slog.Error("保存新闻至数据库失败", "error", err)
		slog.Warn("数据库插入失败，但我们将继续发送邮件。")
	}

	subject := fmt.Sprintf("每日60秒早报 - %s", todayDate)
	emailBody := fmt.Sprintf(
		"%s\n\n%s\n【AI 独家点评】:\n\n%s",
		newsContent,
		"==============================",
		aiReply,
	)
	s.emailSender.SendEmail(cfg.Users, subject, emailBody)

	slog.Info("每日任务执行成功。")
}
