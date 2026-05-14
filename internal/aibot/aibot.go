package aibot

import (
	"context"
	"log/slog"
	"time"

	"github.com/openai/openai-go"
	"github.com/openai/openai-go/option"
	"github.com/openai/openai-go/shared"
)

const systemPrompt = "你是一个专业新闻点评人,给你最近几日新闻,你做出总体点评,不需要对每一条新闻点评,用通俗易懂的语言,减少专业性描述,对未来方向做出预测,用纯文本的方式回答我,不用markdown,但是同样需要做好分段"

type AiBot struct {
	client openai.Client
	model  string
}

func New(apiKey, baseURL, model string) *AiBot {
	opts := []option.RequestOption{
		option.WithAPIKey(apiKey),
	}
	if baseURL != "" {
		opts = append(opts, option.WithBaseURL(baseURL))
	}
	return &AiBot{
		client: openai.NewClient(opts...),
		model:  model,
	}
}

func (a *AiBot) Chat(content string) string {
	maxRetries := 3
	for attempt := 1; attempt <= maxRetries; attempt++ {
		slog.Info("正在发送请求至 AI 模型...", "attempt", attempt, "maxRetries", maxRetries)

		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		completion, err := a.client.Chat.Completions.New(ctx, openai.ChatCompletionNewParams{
			Model: shared.ChatModel(a.model),
			Messages: []openai.ChatCompletionMessageParamUnion{
				openai.SystemMessage(systemPrompt),
				openai.UserMessage(content),
			},
		})
		cancel()

		if err != nil {
			slog.Error("与 AI 通信时出错", "error", err)
			if attempt < maxRetries {
				sleepTime := time.Duration(1<<attempt) * time.Second
				slog.Info("将重试 AI 请求", "sleepSeconds", sleepTime.Seconds())
				time.Sleep(sleepTime)
			}
			continue
		}

		if len(completion.Choices) > 0 && completion.Choices[0].Message.Content != "" {
			slog.Info("已收到 AI 模型响应")
			return completion.Choices[0].Message.Content
		}
		return "AI 返回了空内容。"
	}
	return "很抱歉，今日 AI 点评因网络或接口错误暂时无法生成。"
}
