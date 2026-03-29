"""
Получение Steam ID и Rust+ токена для BotConfig.

Запуск:
    python get_token.py

Шаги:
    1. Скрипт зарегистрируется в Firebase и распечатает FCM-токен
    2. Зайди в Rust на сервер
    3. Нажми Escape -> Rust+ -> Pair with Rust+
    4. Вставь FCM-токен из терминала в поле "Device Token" приложения
    5. Подтверди — скрипт поймает уведомление и распечатает steam_id и player_token
"""

import json
import time
from push_receiver.android_fcm_register import AndroidFCM
from push_receiver import PushReceiver

# Константы приложения Rust+ companion (публичные, из APK)
API_KEY             = "AIzaSyB_u2iBGXiMwWzCz6JsBACxCn3YgpHkT2g"
PROJECT_ID          = "rust-companion-app"
GCM_SENDER_ID       = "976529667804"
GMS_APP_ID          = "1:976529667804:android:d6f1ddeb4403b338fea619"
ANDROID_PACKAGE     = "com.facepunch.rust.companion"
ANDROID_CERT        = "E3:44:D3:8C:D2:ED:E0:AD:B7:B1:97:FA:3F:4D:5A:29:CD:AD:96:3F"

def main():
    print("Регистрация в Firebase...")
    try:
        result = AndroidFCM.register(
            api_key=API_KEY,
            project_id=PROJECT_ID,
            gcm_sender_id=GCM_SENDER_ID,
            gms_app_id=GMS_APP_ID,
            android_package_name=ANDROID_PACKAGE,
            android_package_cert=ANDROID_CERT,
        )
    except Exception as e:
        print(f"[ERROR] Не удалось зарегистрироваться в Firebase: {e}")
        return

    fcm_token = result["fcm"]["token"]
    credentials = {
        "fcm_credentials": result["gcm"]
    }

    print("\n" + "="*60)
    print("FCM токен (скопируй его):")
    print(fcm_token)
    print("="*60)
    print("\nДальше:")
    print("1. Открой Rust+ на телефоне ИЛИ зайди в игру -> Escape -> Rust+")
    print("2. Нажми 'Pair with Rust+' в игре")
    print("3. Ожидаю уведомление... (Ctrl+C для выхода)\n")

    received = {"done": False}

    def on_notification(obj, notification, data_message):
        try:
            data = {}
            if hasattr(notification, "data"):
                data = notification.data
            elif isinstance(notification, dict):
                data = notification.get("data", notification)

            steam_id    = data.get("steamId") or data.get("steam_id")
            player_token = data.get("playerToken") or data.get("player_token")

            if steam_id and player_token:
                print("\n" + "="*60)
                print("[OK] Токен получен!")
                print(f"  Steam ID      : {steam_id}")
                print(f"  Player Token  : {player_token}")
                print("="*60)
                print("\nВставь эти значения в Django Admin -> BotConfig")
                received["done"] = True
            else:
                print(f"[INFO] Уведомление получено, но нет токена: {data}")
        except Exception as e:
            print(f"[WARN] Ошибка обработки уведомления: {e}")
            print(f"  Сырые данные: {notification}")

    try:
        listener = PushReceiver(credentials=credentials["fcm_credentials"])
        listener.listen(callback=on_notification)
    except KeyboardInterrupt:
        print("\nОстановлено.")

if __name__ == "__main__":
    main()
