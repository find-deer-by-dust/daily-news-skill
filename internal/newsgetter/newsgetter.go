package newsgetter

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

var numberPrefixRe = regexp.MustCompile(`^\d+、\s*`)

type fatalError struct{ msg string }

func (e *fatalError) Error() string { return e.msg }

type NewsGetter struct {
	apiURL    string
	token     string
	client    *http.Client
	sleepFunc func(time.Duration)
}

type newsAPIResponse struct {
	Code int    `json:"code"`
	Msg  string `json:"msg"`
	Data struct {
		Date string   `json:"date"`
		News []string `json:"news"`
	} `json:"data"`
}

func New(apiURL, token string) *NewsGetter {
	return &NewsGetter{
		apiURL:    apiURL,
		token:     token,
		client:    &http.Client{Timeout: 15 * time.Second},
		sleepFunc: time.Sleep,
	}
}

func (n *NewsGetter) GetDailyNews() string {
	maxRetries := 10
	for attempt := 1; attempt <= maxRetries; attempt++ {
		slog.Info("正在从 API 获取新闻...", "attempt", attempt, "maxRetries", maxRetries)

		content, err := n.fetch()
		if err != nil {
			// Non-retryable errors — abort immediately
			if _, ok := err.(*fatalError); ok {
				slog.Error("获取新闻失败（不可重试）", "error", err)
				return ""
			}
			slog.Error("获取新闻失败", "error", err)
			if attempt < maxRetries {
				sleepTime := time.Duration(1<<attempt) * time.Second
				slog.Info("将重试", "sleepSeconds", sleepTime.Seconds())
				n.sleepFunc(sleepTime)
			}
			continue
		}
		return content
	}
	slog.Error("所有获取新闻的尝试均失败")
	return ""
}

func (n *NewsGetter) fetch() (string, error) {
	data := url.Values{}
	data.Set("token", n.token)

	resp, err := n.client.Post(n.apiURL, "application/x-www-form-urlencoded", strings.NewReader(data.Encode()))
	if err != nil {
		return "", fmt.Errorf("网络错误: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("读取响应失败: %w", err)
	}

	var apiResp newsAPIResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return "", fmt.Errorf("解析JSON响应出错: %w", err)
	}

	if apiResp.Code != 200 {
		return "", &fatalError{fmt.Sprintf("API返回错误: %s", apiResp.Msg)}
	}

	todayStr := time.Now().Format("2006-01-02")
	if apiResp.Data.Date != "" && apiResp.Data.Date != todayStr {
		return "", fmt.Errorf("新闻尚未更新，当前日期: %s", apiResp.Data.Date)
	}

	if len(apiResp.Data.News) == 0 {
		return "", &fatalError{msg: "API响应中未找到新闻项"}
	}

	formatted := make([]string, 0, len(apiResp.Data.News))
	for _, item := range apiResp.Data.News {
		clean := numberPrefixRe.ReplaceAllString(item, "")
		formatted = append(formatted, strings.TrimSpace(clean))
	}

	return strings.Join(formatted, "\n\n"), nil
}
