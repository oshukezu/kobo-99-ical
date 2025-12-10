"""資料模型定義"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class BookItem:
    """書籍項目"""
    title: str
    book_url: str
    article_url: str
    date: date
    week: int
    year: int

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "title": self.title,
            "book_url": self.book_url,
            "article_url": self.article_url,
            "date": self.date.isoformat(),
            "week": self.week,
            "year": self.year,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BookItem":
        """從字典創建"""
        return cls(
            title=data["title"],
            book_url=data["book_url"],
            article_url=data["article_url"],
            date=date.fromisoformat(data["date"]),
            week=data["week"],
            year=data["year"],
        )

    def __hash__(self) -> int:
        """用於去重"""
        return hash((self.book_url, self.date.isoformat()))

    def __eq__(self, other) -> bool:
        """比較是否相同"""
        if not isinstance(other, BookItem):
            return False
        return self.book_url == other.book_url and self.date == other.date

