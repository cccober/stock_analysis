import pandas as pd
import unittest

from src.data_sync.stock_data_sync import StockDataSync


class NewsAggregationTest(unittest.TestCase):
    def test_merge_news_frames_deduplicates_and_sorts(self):
        eastmoney = pd.DataFrame(
            [
                {
                    "title": "Alpha",
                    "datetime": "2026-05-04 09:30:00",
                    "url": "https://example.com/a",
                    "src": "eastmoney",
                },
                {
                    "title": "Beta",
                    "datetime": "2026-05-04 09:20:00",
                    "url": "https://example.com/b",
                    "src": "eastmoney",
                },
            ]
        )
        sina = pd.DataFrame(
            [
                {
                    "title": "Alpha",
                    "datetime": "2026-05-04 09:30:00",
                    "url": "https://example.com/a",
                    "src": "sina",
                },
                {
                    "title": "Gamma",
                    "datetime": "2026-05-04 10:00:00",
                    "url": "https://example.com/c",
                    "src": "sina",
                },
            ]
        )

        merged = StockDataSync.merge_news_frames([eastmoney, sina], limit=3)

        self.assertEqual(merged["title"].tolist(), ["Gamma", "Alpha", "Beta"])
        self.assertEqual(merged["src"].tolist(), ["sina", "eastmoney", "eastmoney"])


if __name__ == "__main__":
    unittest.main()
