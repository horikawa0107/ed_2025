import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta,timezone
from page import app   # Flask アプリを import
from email.utils import parsedate_to_datetime
# from django.utils import timezone

# --- SQL の呼び出し内容をテストする（asu_001） ---
def test_asu_001_correct_tables_used():

    with patch("page.get_db_connection") as mock_conn:
        # --- モックカーソル準備 ---
        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor

        # comfort_data の最新データ（UI参照データ）
        mock_cursor.fetchone.side_effect = [
            {"processed_sensor_data_id": 100, "timestamp": datetime.now()},
            {"id": 100},  # processed_sensor_data の 1件
            {"cnt": 10},  # データ件数
        ]
        mock_cursor.fetchall.return_value = []  # 最新10件ログ

        client = app.test_client()
        response = client.post("/look", data={"room_id": "1", "room_name": "Room1"})

        assert response.status_code == 200

        # SQL が正しいテーブル名を含んでいるかチェック
        executed_sqls = [call.args[0] for call in mock_cursor.execute.call_args_list]

        assert any("FROM comfort_data" in sql for sql in executed_sqls)
        assert any("FROM processed_sensor_data" in sql for sql in executed_sqls)

def test_asu_002_latest_timestamp_within_30min():

    now = datetime.now(timezone.utc)
    test_timestamp = now - timedelta(minutes=10)  # 10分前 → 有効

    with patch("page.get_db_connection") as mock_conn:

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor

        # comfort_data の timestamp にテスト時刻を返す
        mock_cursor.fetchone.side_effect = [
            {"processed_sensor_data_id": 200, "timestamp": test_timestamp},
            {"id": 200},
            {"cnt": 5},
        ]
        mock_cursor.fetchall.return_value = []

        client = app.test_client()
        response = client.get("/api/latest/1")

        assert response.status_code == 200
        json_data = response.get_json()

        ts = parsedate_to_datetime(json_data["predicted_data"]["timestamp"])
        

        # --- 30分以内か ---
        assert now - timedelta(minutes=30) <= ts <= now + timedelta(minutes=30)
