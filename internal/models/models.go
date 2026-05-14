package models

import "time"

type DailyNews struct {
	ID      int
	Date    time.Time
	News    string
	AiReply string
}
