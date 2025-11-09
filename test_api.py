import requests

def get_devices_connected_to_ap(api_token: str, site_id: str, ap_id: str):
    """
    MIST APIを使用して、特定のAPに接続しているデバイス情報を取得する関数

    Parameters:
        api_token (str): MIST APIトークン
        site_id (str): サイトID
        ap_id (str): アクセスポイントID

    Returns:
        list: APに接続しているデバイス情報のリスト
    """
    url = f"https://api.mist.com/api/v1/sites/{site_id}/clients"
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return []

    clients = response.json()
    connected_devices = [c for c in clients if c.get("ap_id") == ap_id]

    return connected_devices


# === 使用例 ===
if __name__ == "__main__":
    API_TOKEN = "YOUR_MIST_API_TOKEN"
    SITE_ID = "YOUR_SITE_ID"
    AP_ID = "YOUR_AP_ID"

    devices = get_devices_connected_to_ap(API_TOKEN, SITE_ID, AP_ID)

    for d in devices:
        print(f"Device: {d['mac']}  User: {d.get('user_name', 'N/A')}  RSSI: {d.get('rssi')}")

# import requests

# def count_long_connected_devices(api_token: str, site_id: str, ap_id: str, threshold_minutes: int = 30) -> int:
#     """
#     特定のAPに接続しているデバイスのうち、uptimeが指定時間以上のデバイス数を返す関数。

#     Parameters:
#         api_token (str): MIST APIトークン
#         site_id (str): サイトID
#         ap_id (str): APのID
#         threshold_minutes (int): uptimeの閾値（分単位、デフォルト30分）

#     Returns:
#         int: uptimeが閾値以上のデバイス数
#     """
#     url = f"https://api.mist.com/api/v1/sites/{site_id}/clients"
#     headers = {
#         "Authorization": f"Token {api_token}",
#         "Content-Type": "application/json"
#     }

#     response = requests.get(url, headers=headers)
#     if response.status_code != 200:
#         print(f"Error {response.status_code}: {response.text}")
#         return 0

#     clients = response.json()

#     # uptimeがthreshold_minutes分以上のデバイスをカウント
#     threshold_seconds = threshold_minutes * 60
#     long_connected_devices = [
#         c for c in clients
#         if c.get("ap_id") == ap_id and c.get("uptime", 0) >= threshold_seconds
#     ]

#     return len(long_connected_devices)


# # === 使用例 ===
# if __name__ == "__main__":
#     API_TOKEN = "YOUR_MIST_API_TOKEN"
#     SITE_ID = "YOUR_SITE_ID"
#     AP_ID = "YOUR_AP_ID"

#     count = count_long_connected_devices(API_TOKEN, SITE_ID, AP_ID)
#     print(f"30分以上接続しているデバイス数: {count}")