package mysql

import (
	"database/sql"
	"fmt"
	"log/slog"
	"time"

	"emailBot/internal/models"

	_ "github.com/go-sql-driver/mysql"
)

type MysqlConnector struct {
	db *sql.DB
}

func New(host, user, password, dbName string) (*MysqlConnector, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:3306)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		user, password, host, dbName)

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("连接数据库时出错: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("数据库Ping失败: %w", err)
	}

	slog.Info("已连接到数据库")
	return &MysqlConnector{db: db}, nil
}

func (m *MysqlConnector) Close() {
	if m.db != nil {
		m.db.Close()
		slog.Info("数据库连接已关闭")
	}
}

func (m *MysqlConnector) Insert(date time.Time, news, aiReply string) error {
	sqlStr := "INSERT INTO dailyNews(date, news, aiReply) VALUES (?, ?, ?);"

	tx, err := m.db.Begin()
	if err != nil {
		return fmt.Errorf("开启事务失败: %w", err)
	}
	defer tx.Rollback()

	_, err = tx.Exec(sqlStr, date.Format("2006-01-02"), news, aiReply)
	if err != nil {
		return fmt.Errorf("插入新闻时出错: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("提交事务失败: %w", err)
	}

	slog.Info("已将新闻插入数据库")
	return nil
}

func (m *MysqlConnector) SelectByDate(date time.Time) (*models.DailyNews, error) {
	sqlStr := "SELECT * FROM dailyNews WHERE date = ?;"
	row := m.db.QueryRow(sqlStr, date.Format("2006-01-02"))

	news := &models.DailyNews{}
	var dateStr string
	err := row.Scan(&news.ID, &dateStr, &news.News, &news.AiReply)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("按日期查询时出错: %w", err)
	}

	news.Date, _ = time.Parse("2006-01-02", dateStr)
	return news, nil
}

func (m *MysqlConnector) HaveNews(date time.Time) bool {
	if m.db == nil {
		return false
	}
	result, err := m.SelectByDate(date)
	if err != nil {
		slog.Error("检查新闻是否存在时出错", "error", err)
		return false
	}
	return result != nil
}

func (m *MysqlConnector) GetNearestNews(limit int) string {
	sqlStr := "SELECT * FROM dailyNews ORDER BY date DESC LIMIT ?;"
	rows, err := m.db.Query(sqlStr, limit)
	if err != nil {
		slog.Error("获取最近新闻时出错", "error", err)
		return ""
	}
	defer rows.Close()

	var items []string
	for rows.Next() {
		var id int
		var dateStr, news, aiReply string
		if err := rows.Scan(&id, &dateStr, &news, &aiReply); err != nil {
			slog.Error("扫描新闻行时出错", "error", err)
			continue
		}
		items = append(items, fmt.Sprintf("%s:%s", dateStr, news))
	}

	return stringsJoin(items, "\n")
}

func stringsJoin(items []string, sep string) string {
	result := ""
	for i, item := range items {
		if i > 0 {
			result += sep
		}
		result += item
	}
	return result
}
