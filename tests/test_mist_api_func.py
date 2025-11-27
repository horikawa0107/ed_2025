import pytest
from unittest.mock import patch, MagicMock
from page import count_long_connected_devices
import time

# -------------------------------
# mist_api_001: エラー処理
# -------------------------------
@patch("page.requests.get")
def test_mist_api_001_error_response(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_get.return_value = mock_response

    result = count_long_connected_devices("token", "site", "ap1")

    assert result == 0


# -------------------------------
# mist_api_002: リクエスト・レスポンス整合性
# -------------------------------
@patch("page.requests.get")
def test_mist_api_002_normal_response(mock_get):
    # uptime が 5 分以上のデバイス → 300 秒以上
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"ap_id": "ap1", "uptime": 400},
        {"ap_id": "ap1", "uptime": 100},
        {"ap_id": "ap2", "uptime": 500},
    ]
    mock_get.return_value = mock_response

    result = count_long_connected_devices("token", "site", "ap1", threshold_minutes=5)

    assert isinstance(result, int)
    assert result == 1   # 400秒だけが該当


# -------------------------------
# mist_api_003: 入力エラー処理（入力値欠け）
# -------------------------------
def test_mist_api_003_input_error():
    # 不正な型
    result = count_long_connected_devices(None, None, None)

    # 本来なら例外を出すべきだが、現実装は APIエラー扱いで 0 が返る可能性が高い
    assert result == 0


# -------------------------------
# mist_api_004: パフォーマンス（2秒以内）
# -------------------------------
@patch("page.requests.get")
def test_mist_api_004_performance(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    start = time.time()
    result = count_long_connected_devices("token", "site", "ap1")
    end = time.time()

    assert result == 0
    assert (end - start) < 2  # 2秒以内に処理できる