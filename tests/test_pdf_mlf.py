import pandas as pd
from unittest.mock import patch, MagicMock

# ---- テスト対象の関数を import ----
from page import load_data_from_mysql, get_lateset_processed_sensor_data


# ==========================================================
#  pl_001 前処理済みデータの取得（テーブル名の確認）
# ==========================================================
def test_pl_001_table_names():

    with patch("page.get_db_connection") as mock_conn:

        # --- SQL結果のダミー DataFrame ---
        dummy_df = pd.DataFrame([{
            "avg_temperature": 25.0,
            "avg_humidity": 60.0,
            "avg_light": 300,
            "avg_pressure": 1000,
            "avg_sound_level": 40,
            "month": 1,
            "score_from_avg_device_count": 5
        }])

        # --- read_sql をモック化 ---
        mock_conn.return_value = MagicMock()
        with patch("pandas.read_sql", return_value=dummy_df) as mock_read_sql:

            # processed_sensor_data_for_ml 用
            load_data_from_mysql()

            # processed_sensor_data 用
            get_lateset_processed_sensor_data()

            # SQL が正しいテーブルを参照しているか確認
            calls = [call.args[0] for call in mock_read_sql.call_args_list]

            assert any("FROM processed_sensor_data_for_ml" in sql for sql in calls)
            assert any("FROM processed_sensor_data" in sql for sql in calls)


def test_pl_002_record_count():

    with patch("page.get_db_connection") as mock_conn:

        # テスト用に 10 件のダミーデータ
        dummy_records = []
        for i in range(10):
            dummy_records.append({
                "avg_temperature": 25 + i,
                "avg_humidity": 50 + i,
                "avg_light": 300 + i,
                "avg_pressure": 1000 + i,
                "avg_sound_level": 30 + i,
                "month": 1,
                "score_from_avg_device_count": i,
            })

        dummy_df = pd.DataFrame(dummy_records)

        # pandas.read_sql をモック化して dummy_df を返すようにする
        with patch("pandas.read_sql", return_value=dummy_df) as mock_read_sql:

            df = load_data_from_mysql()

            # 返却される行数が 10（テスト用 limit）であること
            assert len(df) == 10
