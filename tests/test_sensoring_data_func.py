import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from page import periodic_scan
from page import parse_format_04


# ==============================
#  共通：テスト用固定アドレス
# ==============================
TEST_ADDRESS = "OMRON_ADDRESS_1"


# ===========================================================
# 001 デバイス未検出
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_001_no_device_detected():
    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {}

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.log_error") as mock_log, \
         patch("page.asyncio.sleep", new=AsyncMock()):

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_log.assert_any_call(f"{TEST_ADDRESS}のデバイスが見つかりません。")


# ===========================================================
# 002 デバイス検出 → manufacturer_data 取得に進む
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_002_device_detected():
    adv_mock = MagicMock()
    adv_mock.manufacturer_data = {0x02ff: b"dummy_raw_data"}

    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {
        TEST_ADDRESS: (None, adv_mock)
    }

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.OMRON_MANUFACTURER_ID", 0x02ff), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.parse_format_04", return_value={"temperature": 25}), \
         patch("page.asyncio.sleep", new=AsyncMock()), \
         patch("builtins.print") as mock_print:
        

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_print.assert_any_call(f"[SUCCESS] データ取得成功({TEST_ADDRESS}): {{'temperature': 25}}")


# ===========================================================
# 003 manufacturer_data 正常 → parse_format_04 呼び出し
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_003_manufacturer_data_present():
    adv_mock = MagicMock()
    adv_mock.manufacturer_data = {0x02ff: b"valid_data"}

    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {
        TEST_ADDRESS: (None, adv_mock)
    }

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.OMRON_MANUFACTURER_ID", 0x02ff), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.parse_format_04") as mock_parse, \
         patch("page.asyncio.sleep", new=AsyncMock()):

        mock_parse.return_value = {"temperature": 24.5}

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_parse.assert_called_once_with(b"valid_data")


# ===========================================================
# 004 manufacturer_data が空 → エラー出力
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_004_missing_manufacturer_data():
    adv_mock = MagicMock()
    adv_mock.manufacturer_data = {}  # データなし

    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {
        TEST_ADDRESS: (None, adv_mock)
    }

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.OMRON_MANUFACTURER_ID", 0x02ff), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.log_error") as mock_log, \
         patch("page.asyncio.sleep", new=AsyncMock()):

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_log.assert_any_call(f"{TEST_ADDRESS}のManufacturer data が見つかりません。")


# ===========================================================
# 005 parse_format_04 が正しい dict を返す
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_005_valid_parse_format():
    adv_mock = MagicMock()
    adv_mock.manufacturer_data = {0x02ff: b"20bytes_valid_data"}

    parsed_data = {
        "temperature": 23.1,
        "humidity": 55,
        "light": 300,
        "pressure": 1005,
        "sound_level": 40,
        "battery": 85,
        "month": 11
    }

    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {
        TEST_ADDRESS: (None, adv_mock)
    }

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.OMRON_MANUFACTURER_ID", 0x02ff), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.parse_format_04", return_value=parsed_data), \
         patch("page.asyncio.sleep", new=AsyncMock()), \
         patch("builtins.print") as mock_print:

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_print.assert_any_call(f"[SUCCESS] データ取得成功({TEST_ADDRESS}): {parsed_data}")


# ===========================================================
# 006 parse_format_04 が None → 解析失敗
# ===========================================================
@pytest.mark.asyncio
async def test_sensor_006_invalid_data_length():
    adv_mock = MagicMock()
    adv_mock.manufacturer_data = {0x02ff: b"too_short"}

    fake_scanner = MagicMock()
    fake_scanner.start = AsyncMock()
    fake_scanner.stop = AsyncMock()
    fake_scanner.discovered_devices_and_advertisement_data = {
        TEST_ADDRESS: (None, adv_mock)
    }

    with patch("page.OMRON_ADDRESSES", [TEST_ADDRESS]), \
         patch("page.ROOM_IDS", [1]), \
         patch("page.OMRON_MANUFACTURER_ID", 0x02ff), \
         patch("page.BleakScanner", return_value=fake_scanner), \
         patch("page.parse_format_04", return_value=None), \
         patch("page.log_error") as mock_log, \
         patch("page.asyncio.sleep", new=AsyncMock()):

        await asyncio.wait_for(periodic_scan(interval=0, once=True), timeout=0.1)

        mock_log.assert_any_call(f"{TEST_ADDRESS}のデータフォーマットの解析に失敗しました。")
