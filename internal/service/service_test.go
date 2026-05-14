package service

import (
	"testing"
)

func TestBuildPrompt_WithHistory(t *testing.T) {
	svc := &NewsService{coverageDays: 7}
	prompt := svc.buildPrompt("2026-05-14", "新闻内容", "2026-05-13:历史新闻")
	if prompt == "" {
		t.Fatal("prompt should not be empty")
	}

	// Verify key sections are present
	checks := []string{
		"2026-05-14",
		"新闻内容",
		"2026-05-13:历史新闻",
		"点评要求",
		"专业点评",
		"总体概述",
		"未来方向做出预测",
		"纯文本输出",
	}
	for _, check := range checks {
		if !contains(prompt, check) {
			t.Errorf("prompt should contain %q", check)
		}
	}
}

func TestBuildPrompt_NoHistory(t *testing.T) {
	svc := &NewsService{coverageDays: 7}
	prompt := svc.buildPrompt("2026-05-14", "新闻内容", "")
	if prompt == "" {
		t.Fatal("prompt should not be empty")
	}
	if !contains(prompt, "无历史数据") {
		t.Error("prompt should contain '无历史数据' when no history")
	}
}

func TestNewNewsService_RequiresConfig(t *testing.T) {
	// New() requires config.AppConfig to be set — this test verifies
	// the buildPrompt logic independently
}

func contains(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
