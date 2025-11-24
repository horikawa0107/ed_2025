import pytest
from unittest.mock import patch, MagicMock

from page import predict_comfort_score, insert_comfort_data, generate_advice


def test_la_001_advice_input_matches_prediction_input():

    # --- 1) 前処理済みデータ（predict_comfort_score の入力） ---
    preprocessed_data = {
        "avg_temperature": 28.0,
        "avg_humidity": 65.0,
        "avg_light": 800,
        "avg_pressure": 999,
        "avg_sound_level": 75,
        "month": 8,
    }

    # --- 2) アドバイス生成に渡されるべき元データ（insert_comfort_data の data） ---
    expected_data_for_advice = {
        "temperature": 28.0,
        "humidity": 65.0,
        "light": 800,
        "pressure": 999,
        "sound_level": 75,
        "month": 8,
        "timestamp": "2025-01-01 12:00:00"
    }

    # --- 3) モデル（XGBoost）をモックして快適指数だけ返す ---
    with patch("page.XGBRegressor") as mock_model_class:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.55]
        mock_model_class.return_value = mock_model

        comfort_score = predict_comfort_score(preprocessed_data)

    assert comfort_score == 0.55

    # --- 4) DB write をモックして、generate_advice が実際に呼ばれるようにする ---
    with patch("page.get_db_connection") as mock_conn:

        mock_conn.return_value = MagicMock()

        # generate_advice がどんな返り値でもいい
        # → アドバイス内容は今回のテストでは検証対象外
        # 実際に呼ばれたかチェックする
        with patch("page.generate_advice", wraps=generate_advice) as spy_advice:

            insert_comfort_data(
                data=expected_data_for_advice,
                comfort_score=comfort_score,
                room_id=1,
                processed_sensor_data_id=10
            )

            # ---------- 5) generate_advice が呼ばれたか ----------
            spy_advice.assert_called_once()

            # ---------- 6) 渡された data が完全一致していること（la_001 の核心） ----------
            actual_call_data = spy_advice.call_args[0][0]

            assert actual_call_data == expected_data_for_advice
