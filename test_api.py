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
    url = f"https://mist-api-wrapper.onrender.com/api/v1/sites/{site_id}/stats/clients"
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
    
    API_TOKEN = "abc"
    ORG_ID = "0ec9ad75-1ae0-40b3-bbd8-63ac91775547"
    SITE_ID = "22968ecf-ae7b-4d84-8100-670bb522267b"
    AP_ID = "00000000-0000-0000-1000-5c5b353ecdd7"

    devices = get_devices_connected_to_ap(API_TOKEN, SITE_ID, AP_ID)
    print(devices)

    # for d in devices:
    #     print(f"Device: {d['mac']}  User: {d.get('user_name', 'N/A')}  RSSI: {d.get('rssi')} uptime: {d.get('uptime')}")
        
#horikawafuka2@horikawakazahananoMacBook-Air dev_mysql % python3 test_api.py
#Device: c6c1bf292cba  User: N/A  RSSI: -43 uptime: 151  

# #test_api.py

# API_TOKEN = "ycQduGG1tfVDuCYRdQDbMPoO2qU66UdD8e2xmIeWSHXQ81ZZxSzHYD5w85vCcKiDbL6lWTbwT124q9EnGTlO6fay6X08KF0w"
# ORG_ID = "0ec9ad75-1ae0-40b3-bbd8-63ac91775547"


# import requests

# SITE_ID = "22968ecf-ae7b-4d84-8100-670bb522267b"

# url = f"https://mist-api-wrapper.onrender.com/api/v1/orgs/{ORG_ID}/devices"
# headers = {"Authorization": f"Token {API_TOKEN}"}

# response = requests.get(url, headers=headers)

# if response.status_code != 200:
#     print(f"Error: {response.status_code}, {response.text}")
# else:
#     data = response.json()
#     aps = data.get("results", [])

#     if not aps:
#         print("No APs found or results is empty.")
#     else:
#         for ap in aps:
#             print(f"ap:{ap}")
            
