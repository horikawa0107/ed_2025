import pytest
from page import process_sensor_data, process_sensor_data_for_ml

@pytest.fixture
def test_db(monkeypatch):
    import mysql.connector

    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='password',
        database='ed_2025_test'
    )

    monkeypatch.setattr("page.get_db_connection", lambda: conn)

    cursor = conn.cursor()
    # cursor.execute("DELETE FROM sensor_data")
    # cursor.execute("DELETE FROM sensor_data_for_ml")
    # cursor.execute("DELETE FROM processed_sensor_data")
    # cursor.execute("DELETE FROM processed_sensor_data_for_ml")
    conn.commit()

    return conn


# ★ これを fixture にする！
@pytest.fixture
def test_db_factory(monkeypatch):
    import mysql.connector

    def _factory():
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='password',
            database='ed_2025_test'
        )
        monkeypatch.setattr("page.get_db_connection", lambda: conn)
        return conn

    return _factory


def test_tp01_and_tp02_process_sensor_data(test_db, test_db_factory):
    conn = test_db
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO sensor_data
        (timestamp, room_id, temperature, humidity, pressure, light, sound_level, month, battery)
        VALUES (NOW(), 1, %s, %s, %s, %s, %s, %s, %s)
    """

    sample_values = [
        (23.1, 40.0, 1012, 500, 30.2, 11, 0.8),
        (23.5, 41.0, 1013, 550, 32.1, 11, 0.8),
        (24.0, 42.0, 1014, 600, 33.0, 11, 0.8),
    ]

    for v in sample_values:
        cursor.execute(insert_sql, v)
    conn.commit()

    process_sensor_data("addrX", 1)

    # ★ 新しい接続を作り直す
    conn2 = test_db_factory()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT * FROM processed_sensor_data")
    rows = cursor2.fetchall()
    assert len(rows) == 1

    cursor2.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 3")
    fetched = cursor2.fetchall()
    assert len(fetched) == 3


def test_tp01_and_tp02_process_sensor_data_for_ml(test_db, test_db_factory):
    conn = test_db
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO sensor_data_for_ml
        (timestamp, room_id, temperature, humidity, pressure, light, sound_level, device_count, month, battery)
        VALUES (NOW(), 2, %s, %s, %s, %s, %s, %s, 12, %s)
    """

    sample_values = [
        (22.0, 39.0, 1010, 300, 30.0, 10, 0.8),
        (22.5, 40.0, 1011, 350, 31.0, 10, 0.8),
        (23.0, 41.0, 1012, 400, 32.0, 10, 0.8),
    ]

    for v in sample_values:
        cursor.execute(insert_sql, v)
    conn.commit()

    process_sensor_data_for_ml("addrY", 2)

    # ★ 新しい接続を作り直す
    conn2 = test_db_factory()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT * FROM processed_sensor_data_for_ml")
    rows = cursor2.fetchall()
    assert len(rows) == 1

    cursor2.execute("SELECT * FROM sensor_data_for_ml ORDER BY timestamp DESC LIMIT 3")
    fetched = cursor2.fetchall()
    assert len(fetched) == 3
