import pytest
from page import process_sensor_data
from page import process_sensor_data_for_ml

# ============================
# Fake DB Classes
# ============================

class FakeCursor:
    def __init__(self, rows=None, raise_error=False):
        self.rows = rows or []
        self.closed = False
        self.execute_called = False
        self.execute_sql = None
        self.raise_error = raise_error

    def execute(self, sql, params=None):
        self.execute_called = True
        self.execute_sql = sql
        if self.raise_error:
            raise Exception("SQL ERROR")

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None, raise_error=False):
        self.rows = rows
        self.raise_error = raise_error
        self.cursor_created = 0
        self.committed = False
        self.closed = False
        self.insert_values = None

    def cursor(self, dictionary=False):
        self.cursor_created += 1
        return FakeCursor(rows=self.rows, raise_error=self.raise_error)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


# ============================
# Fake log_error
# ============================
class LogCapture:
    def __init__(self):
        self.messages = []

    def __call__(self, msg):
        self.messages.append(msg)


# ==========================================================
# process_001：DB接続成功テスト
# ==========================================================
def test_process_001_db_connect(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # 3件与えて正常に通るようにする
    rows = [
        {"timestamp": 1, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5, "battery": 90, "month": 1},
        {"timestamp": 2, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5, "battery": 90, "month": 1},
        {"timestamp": 3, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5, "battery": 90, "month": 1},
    ]
    fake_conn.rows = rows

    process_sensor_data("addr1", 1)

    assert fake_conn.cursor_created > 0, "DB接続が行われていません"

def test_process_001_db_for_ml_connect(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # 3件与えて正常に通るようにする
    rows = [
        {"timestamp": 1, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5,"device_count":5, "battery": 90, "month": 1},
        {"timestamp": 2, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5,"device_count":5, "battery": 90, "month": 1},
        {"timestamp": 3, "temperature": 1, "humidity": 2, "light": 3, "pressure": 4, "sound_level": 5,"device_count":5, "battery": 90, "month": 1},
    ]
    fake_conn.rows = rows

    process_sensor_data_for_ml("addr1", 1)

    assert fake_conn.cursor_created > 0, "DB接続が行われていません"


# ==========================================================
# process_003：データが3件未満のときスキップ
# ==========================================================
def test_process_002_less_than_three(monkeypatch):
    logs = LogCapture()

    fake_conn = FakeConnection(rows=[{"dummy": 1}])  # 1件のみ
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data("addrX", 1)

    assert "3件未満" in logs.messages[0], "3件未満の警告ログが残っていない"
    assert fake_conn.committed is False, "スキップ時に commit されてはいけない"
    assert fake_conn.closed, "スキップ時にも conn.close() が呼ばれるべき"

def test_process_002_less_than_three_for_ml(monkeypatch):
    logs = LogCapture()

    fake_conn = FakeConnection(rows=[{"dummy": 1}])  # 1件のみ
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data_for_ml("addrX", 1)

    assert "3件未満" in logs.messages[0], "3件未満の警告ログが残っていない"
    assert fake_conn.committed is False, "スキップ時に commit されてはいけない"
    assert fake_conn.closed, "スキップ時にも conn.close() が呼ばれるべき"



# ==========================================================
# process_003（平均値の四捨五入確認）
# ==========================================================
def test_process_003_rounding_for_ml(monkeypatch):
    # 平均 = (20.123 + 20.456 + 20.789)/3 = 20.456
    # → 四捨五入で 20.5 になる（コードは float のままなので 20.456 のまま → 仕様要確認）
    rows = [
        {"timestamp": 10, "temperature": 20.123, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "device_count":5,"battery": 90, "month": 1},
        {"timestamp": 10, "temperature": 20.456, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "device_count":5,"battery": 90, "month": 1},
        {"timestamp": 10, "temperature": 20.789, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "device_count":5,"battery": 90, "month": 1},
    ]

    fake_conn = FakeConnection(rows=rows)
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # INSERT された値を記録するようにカスタム cursor を差し替え
    def fake_cursor(*args, **kwargs):
        c = FakeCursor(rows=rows)
        def execute(sql, params=None):
            fake_conn.insert_values = params
        c.execute = execute
        return c

    fake_conn.cursor = fake_cursor

    process_sensor_data_for_ml("addr1", 1)

    inserted = fake_conn.insert_values
    assert inserted is not None, "INSERT が呼ばれていない"
    assert inserted[2] == 20.5, "平均値の丸めが正しくありません"

def test_process_003_rounding(monkeypatch):
    # 平均 = (20.123 + 20.456 + 20.789)/3 = 20.456
    # → 四捨五入で 20.5 になる（コードは float のままなので 20.456 のまま → 仕様要確認）
    rows = [
        {"timestamp": 10, "temperature": 20.123, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "battery": 90, "month": 1},
        {"timestamp": 10, "temperature": 20.456, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "battery": 90, "month": 1},
        {"timestamp": 10, "temperature": 20.789, "humidity": 0, "light": 0, "pressure": 0, "sound_level": 0, "battery": 90, "month": 1},
    ]

    fake_conn = FakeConnection(rows=rows)
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    # INSERT された値を記録するようにカスタム cursor を差し替え
    def fake_cursor(*args, **kwargs):
        c = FakeCursor(rows=rows)
        def execute(sql, params=None):
            fake_conn.insert_values = params
        c.execute = execute
        return c

    fake_conn.cursor = fake_cursor

    process_sensor_data("addr1", 1)

    inserted = fake_conn.insert_values
    assert inserted is not None, "INSERT が呼ばれていない"
    assert inserted[2] == 20.5, "平均値の丸めが正しくありません"


# ==========================================================
# process_004：平均値計算精度
# ==========================================================
def test_process_004_calculation(monkeypatch):
    rows = [
        {"timestamp": 10, "temperature": 10, "humidity": 30, "light": 15, "pressure": 20, "sound_level": 40, "battery": 99, "month": 2},
        {"timestamp": 11, "temperature": 20, "humidity": 40, "light": 25, "pressure": 30, "sound_level": 50, "battery": 99, "month": 2},
        {"timestamp": 12, "temperature": 30, "humidity": 50, "light": 35, "pressure": 40, "sound_level": 60, "battery": 99, "month": 2},
    ]

    fake_conn = FakeConnection(rows=rows)
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    def fake_cursor(*args, **kwargs):
        c = FakeCursor(rows=rows)
        def execute(sql, params=None):
            fake_conn.insert_values = params
        c.execute = execute
        return c
    fake_conn.cursor = fake_cursor

    process_sensor_data("addr1", 1)

    t = sum([10,20,30])/3
    h = sum([30,40,50])/3
    l = sum([15,25,35])/3

    inserted = fake_conn.insert_values
    assert abs(inserted[2] - t) < 0.001
    assert abs(inserted[3] - h) < 0.001
    assert abs(inserted[5] - l) < 0.001


def test_process_004_calculation_for_ml(monkeypatch):
    rows = [
        {"timestamp": 10, "temperature": 10, "humidity": 30, "light": 15, "pressure": 20, "sound_level": 40,"device_count":5, "battery": 99, "month": 2},
        {"timestamp": 11, "temperature": 20, "humidity": 40, "light": 25, "pressure": 30, "sound_level": 50,"device_count":6, "battery": 99, "month": 2},
        {"timestamp": 12, "temperature": 30, "humidity": 50, "light": 35, "pressure": 40, "sound_level": 60,"device_count":7, "battery": 99, "month": 2},
    ]

    fake_conn = FakeConnection(rows=rows)
    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)

    def fake_cursor(*args, **kwargs):
        c = FakeCursor(rows=rows)
        def execute(sql, params=None):
            fake_conn.insert_values = params
        c.execute = execute
        return c
    fake_conn.cursor = fake_cursor

    process_sensor_data("addr1", 1)

    t = sum([10,20,30])/3
    h = sum([30,40,50])/3
    l = sum([15,25,35])/3

    inserted = fake_conn.insert_values
    assert abs(inserted[2] - t) < 0.001
    assert abs(inserted[3] - h) < 0.001
    assert abs(inserted[5] - l) < 0.001


# ==========================================================
# process_008：空データでもクラッシュしない
# ==========================================================
def test_process_008_empty_data(monkeypatch):
    fake_conn = FakeConnection(rows=[])
    logs = LogCapture()

    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data("addrX", 2)

    assert any("3件未満" in msg for msg in logs.messages), "空データでスキップされていない"

def test_process_008_empty_data_for_ml(monkeypatch):
    fake_conn = FakeConnection(rows=[])
    logs = LogCapture()

    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data_for_ml("addrX", 2)

    assert any("3件未満" in msg for msg in logs.messages), "空データでスキップされていない"



# ==========================================================
# process_009：DBエラー（SQLエラー）時の挙動確認
# ==========================================================
def test_process_009_sql_error(monkeypatch):
    logs = LogCapture()
    fake_conn = FakeConnection(rows=[], raise_error=True)

    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data("addrErr", 9)

    assert any("エラー" in msg for msg in logs.messages), "SQLエラー時のログが記録されていません"
    assert fake_conn.closed, "エラー時でも conn.close() が呼ばれていません"

def test_process_009_sql_error_for_ml(monkeypatch):
    logs = LogCapture()
    fake_conn = FakeConnection(rows=[], raise_error=True)

    monkeypatch.setattr("page.get_db_connection", lambda: fake_conn)
    monkeypatch.setattr("page.log_error", logs)

    process_sensor_data_for_ml("addrErr", 9)

    assert any("エラー" in msg for msg in logs.messages), "SQLエラー時のログが記録されていません"
    assert fake_conn.closed, "エラー時でも conn.close() が呼ばれていません"

