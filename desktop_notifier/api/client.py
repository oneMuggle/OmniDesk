import requests
from PyQt6.QtCore import QDate, QDateTime, Qt


class ApiClient:
    BASE_URL = "http://127.0.0.1:8000/api"

    def __init__(self):
        pass

    def login(self, username, password):
        try:
            response = requests.post(
                f"{self.BASE_URL}/token/",
                data={"username": username, "password": password},
                timeout=5
            )
            response.raise_for_status()
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {e}")
        return None

    def refresh_token(self, refresh_token):
        try:
            response = requests.post(
                f"{self.BASE_URL}/token/refresh/",
                json={"refresh": refresh_token},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("access")
        except requests.exceptions.RequestException:
            pass
        return None

    def register(self, username, password):
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/registration/",
                json={"username": username, "password": password},
                timeout=5
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Registration failed: {e}")
        return None

    def get_schedules(self, access_token):
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        url = f"{self.BASE_URL}/events/schedules/?duty_date={today_str}"
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch schedules: {e}")
        return []

    def get_experiments(self, access_token):
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        url = f"{self.BASE_URL}/events/trials/?start_date__lte={today_str}&end_date__gte={today_str}"
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch experiments: {e}")
        return []

    def get_bookings(self, access_token):
        url = f"{self.BASE_URL}/meeting-rooms/meeting-room-bookings/this-week/"
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            # Filter for today's bookings on the client side
            today = QDate.currentDate()
            today_bookings = []
            for item in response.json():
                start_time = QDateTime.fromString(item.get('start_time', ''), Qt.DateFormat.ISODate)
                if start_time.date() == today:
                    today_bookings.append(item)
            return today_bookings
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch bookings: {e}")
        return []