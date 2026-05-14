package newsgetter

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// newTestNewsGetter creates a NewsGetter with no-op sleep for fast tests.
func newTestNewsGetter(url, token string) *NewsGetter {
	ng := New(url, token)
	ng.sleepFunc = func(d time.Duration) {} // no-op
	return ng
}

func TestGetDailyNews_Success(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.Header.Get("Content-Type") != "application/x-www-form-urlencoded" {
			t.Errorf("unexpected Content-Type: %s", r.Header.Get("Content-Type"))
		}
		resp := newsAPIResponse{}
		resp.Code = 200
		resp.Data.Date = today
		resp.Data.News = []string{"1、新闻一", "2、新闻二", "12、新闻十二"}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	result := ng.GetDailyNews()

	if result == "" {
		t.Fatal("expected news content, got empty string")
	}
	expected := "新闻一\n\n新闻二\n\n新闻十二"
	if result != expected {
		t.Errorf("got %q, want %q", result, expected)
	}
}

func TestGetDailyNews_APINon200(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := newsAPIResponse{Code: 500, Msg: "内部错误"}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	result := ng.GetDailyNews()

	if result != "" {
		t.Errorf("expected empty string for non-200 API response, got %q", result)
	}
}

func TestGetDailyNews_NonRetryableAbortsImmediately(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		resp := newsAPIResponse{Code: 500, Msg: "内部错误"}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	ng.GetDailyNews()

	if callCount != 1 {
		t.Errorf("expected 1 call for non-retryable error, got %d", callCount)
	}
}

func TestGetDailyNews_WrongDate_Retryable(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		resp := newsAPIResponse{}
		resp.Code = 200
		resp.Data.Date = "2020-01-01"
		resp.Data.News = []string{"1、旧闻"}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	result := ng.GetDailyNews()

	if result != "" {
		t.Errorf("expected empty string for wrong-date news, got %q", result)
	}
	// Wrong date is retryable — should have called all 10 retries
	if callCount != 10 {
		t.Errorf("expected 10 calls for retryable wrong-date error, got %d", callCount)
	}
}

func TestGetDailyNews_EmptyNews(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := newsAPIResponse{}
		resp.Code = 200
		resp.Data.Date = today
		resp.Data.News = []string{}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	result := ng.GetDailyNews()

	if result != "" {
		t.Errorf("expected empty string for empty news, got %q", result)
	}
}

func TestFetch_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer server.Close()

	ng := New(server.URL, "test-token")
	_, err := ng.fetch()

	if err == nil {
		t.Error("expected error on server 500")
	}
}

func TestFetch_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("not json"))
	}))
	defer server.Close()

	ng := New(server.URL, "test-token")
	result, err := ng.fetch()

	if err == nil {
		t.Error("expected error on invalid JSON")
	}
	if result != "" {
		t.Errorf("expected empty result on error, got %q", result)
	}
}

func TestGetDailyNews_RetryThenSuccess(t *testing.T) {
	today := time.Now().Format("2006-01-02")
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		if callCount < 3 {
			w.WriteHeader(500)
			return
		}
		resp := newsAPIResponse{}
		resp.Code = 200
		resp.Data.Date = today
		resp.Data.News = []string{"1、新闻"}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	ng := newTestNewsGetter(server.URL, "test-token")
	result := ng.GetDailyNews()

	if result != "新闻" {
		t.Errorf("got %q, want %q", result, "新闻")
	}
	if callCount != 3 {
		t.Errorf("expected 3 calls (2 fails + 1 success), got %d", callCount)
	}
}

func TestNumberPrefixRegex(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"1、新闻标题", "新闻标题"},
		{"12、新闻标题", "新闻标题"},
		{"123、  新闻标题", "新闻标题"},
		{"无序号新闻", "无序号新闻"},
		{"1、第一段\n继续", "第一段\n继续"},
	}
	for _, tc := range tests {
		result := numberPrefixRe.ReplaceAllString(tc.input, "")
		if result != tc.expected {
			t.Errorf("input %q: got %q, want %q", tc.input, result, tc.expected)
		}
	}
}
