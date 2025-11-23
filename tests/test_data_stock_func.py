import pytest
from page import insert_data_to_sensor_data_table
from page import insert_data_to_sensor_data_for_ml_table

# -----------------------------------------------------------
# テスト用 Fake DB オブジェクト
# -----------------------------------------------------------

class FakeCursor:
    def __init__(self):
        self.executed = False
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.executed = True
        self.query = query
        self.params = params

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        pass


# -----------------------------------------------------------
# save_001 正常にデータが挿入される
# -----------------------------------------------------------
def test_save_001_insert_success(monkeypatch):
    fake_conn = FakeConnection()

    # get_db_connection を Fake にすり替え
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # テスト用の入力データ
    data = {
        "timestamp": "2025-02-01 12:00:00",
        "temperature": 25.3,
        "humidity": 40.0,
        "pressure": 1013.0,
        "light": 500,
        "sound_level": 30,
        "month": 2,
        "battery": 95,
    }


    insert_data_to_sensor_data_table(data, room_id=2)

    c = fake_conn.cursor_obj

    # 判定
    assert c.executed, "SQLが実行されていない"
    assert fake_conn.committed, "commitされていない"
    assert c.params[0] == data["timestamp"]
    assert c.params[1] == 2
    assert c.params[2] == data["temperature"]

def test_save_001_insert_success_for_ml(monkeypatch):
    fake_conn = FakeConnection()

    # get_db_connection を Fake にすり替え
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # テスト用の入力データ
    data = {
        "timestamp": "2025-02-01 12:00:00",
        "temperature": 25.3,
        "humidity": 40.0,
        "pressure": 1013.0,
        "light": 500,
        "sound_level": 30,
        "month": 2,
        "battery": 95,
    }


    insert_data_to_sensor_data_for_ml_table(data, room_id=2)

    c = fake_conn.cursor_obj

    # 判定
    assert c.executed, "SQLが実行されていない"
    assert fake_conn.committed, "commitされていない"
    assert c.params[0] == data["timestamp"]
    assert c.params[1] == 2
    assert c.params[2] == data["temperature"]


# -----------------------------------------------------------
# save_002 DB接続エラー（例：接続時に例外発生）
# -----------------------------------------------------------
def test_save_002_db_connect_error(monkeypatch):
    class FakeErrorConnection:
        def __init__(self):
            raise Exception("DB connection failed")

    # get_db_connection をエラーを出す関数に差し替え
    monkeypatch.setattr("page.get_db_connection", lambda: FakeErrorConnection())

    logs = []

    # log_error を記録用に差し替え
    monkeypatch.setattr("page.log_error", lambda msg: logs.append(msg))


    # 実行
    insert_data_to_sensor_data_table({}, room_id=1)

    # 判定 → log_error にメッセージが記録されているか
    assert any("DB" in m or "connection" in m for m in logs), \
        "DB接続エラー時にログが記録されていない"

def test_save_002_db_connect_error_for_ml(monkeypatch):
    class FakeErrorConnection:
        def __init__(self):
            raise Exception("DB connection failed")

    # get_db_connection をエラーを出す関数に差し替え
    monkeypatch.setattr("page.get_db_connection", lambda: FakeErrorConnection())

    logs = []

    # log_error を記録用に差し替え
    monkeypatch.setattr("page.log_error", lambda msg: logs.append(msg))


    # 実行
    insert_data_to_sensor_data_for_ml_table({}, room_id=1)

    # 判定 → log_error にメッセージが記録されているか
    assert any("DB" in m or "connection" in m for m in logs), \
        "DB接続エラー時にログが記録されていない"
