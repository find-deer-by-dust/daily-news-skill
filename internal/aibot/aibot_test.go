package aibot

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestChat_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]interface{}{
			"choices": []map[string]interface{}{
				{
					"message": map[string]interface{}{
						"content": "这是AI的点评内容。",
					},
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	bot := New("test-key", server.URL, "gpt-3.5-turbo")
	result := bot.Chat("请点评新闻")

	if result != "这是AI的点评内容。" {
		t.Errorf("got %q, want %q", result, "这是AI的点评内容。")
	}
}

func TestChat_EmptyContent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]interface{}{
			"choices": []map[string]interface{}{
				{
					"message": map[string]interface{}{
						"content": "",
					},
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	bot := New("test-key", server.URL, "gpt-3.5-turbo")
	result := bot.Chat("请点评新闻")

	if result != "AI 返回了空内容。" {
		t.Errorf("got %q, want empty content message", result)
	}
}

func TestChat_AllRetriesFail(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer server.Close()

	bot := New("test-key", server.URL, "gpt-3.5-turbo")
	result := bot.Chat("请点评新闻")

	expected := "很抱歉，今日 AI 点评因网络或接口错误暂时无法生成。"
	if result != expected {
		t.Errorf("got %q, want %q", result, expected)
	}
}

func TestChat_NoBaseURL_UsesDefault(t *testing.T) {
	bot := New("test-key", "", "gpt-3.5-turbo")
	if bot.model != "gpt-3.5-turbo" {
		t.Errorf("model: got %q, want %q", bot.model, "gpt-3.5-turbo")
	}
}
