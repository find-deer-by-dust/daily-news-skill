import datetime

# DailyNews 表实体类
class DailyNews:
    def __init__(self, id: int, date: datetime.date, news: str, aiReply: str) -> None:
        self.id = id
        self.date = date        # datetime.date 对象
        self.news = news        # 新闻内容
        self.aiReply = aiReply  # AI回应

    def __repr__(self) -> str:
        return f"dailyNews id={self.id} date={self.date} news={self.news} aiReply={self.aiReply}"
