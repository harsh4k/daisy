import requests
from PyQt6.QtCore import QThread, pyqtSignal
import time
import datetime
import threading

class WeatherMonitor(QThread):
    weather_updated = pyqtSignal(dict)
    location_updated = pyqtSignal(bool, str)
    
    def __init__(self, city="Varanasi, India", lat=25.3333, lon=83.0):
        super().__init__()
        self.city = city
        self.lat = lat
        self.lon = lon
        self.running = True
        self.force_update = False
        self.update_interval = 1800              
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._location_lock = threading.Lock()
        self._pending_location = None
        self._location_generation = 0
        self._request_lock = threading.Lock()
        self._request_job = None

    def _request_json(self, url, params):
        # requests cannot cancel an in-flight socket. Keep that bounded I/O off
        # the Qt worker too, so closing Daisy never waits on the network.
        with self._request_lock:
            if self._request_job and self._request_job.is_alive():
                raise RuntimeError("Weather request is still finishing; try again shortly")
            finished = threading.Event()
            result = {}

            def fetch():
                try:
                    response = requests.get(url, params=params, timeout=(2, 3))
                    try:
                        response.raise_for_status()
                        result["data"] = response.json()
                    finally:
                        close = getattr(response, "close", None)
                        if close:
                            close()
                except Exception as exc:
                    result["error"] = exc
                finally:
                    finished.set()

            self._request_job = threading.Thread(target=fetch, daemon=True,
                                                 name="DaisyWeatherRequest")
            self._request_job.start()
        deadline = time.monotonic() + 8
        while not finished.wait(.025):
            if self._stop_event.is_set():
                raise RuntimeError("Weather monitor stopped")
            if time.monotonic() >= deadline:
                raise requests.Timeout("Weather request timed out")
        if self._stop_event.is_set():
            raise RuntimeError("Weather monitor stopped")
        if "error" in result:
            raise result["error"]
        return result["data"]

    def request_location(self, city):
        with self._location_lock:
            self._location_generation += 1
            self._pending_location = (self._location_generation, city)
        self._wake.set()
        
    def set_location(self, city):
        """Legacy synchronous API; GUI callers use request_location instead."""
        return self._set_location(city)

    def _set_location(self, city, generation=None):
        try:
            city = city.strip()
            if not city:
                return False, "Enter a city name"
            res = self._request_json("https://geocoding-api.open-meteo.com/v1/search",
                                     {"name": city, "count": 1, "language": "en", "format": "json"})
            if res.get("results"):
                result = res["results"][0]
                lat, lon = float(result["latitude"]), float(result["longitude"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("Invalid location coordinates")
                with self._location_lock:
                    if generation is not None and generation != self._location_generation:
                        return False, "Location request superseded"
                    self.city = ", ".join(filter(None, (result["name"], result.get("country", ""))))
                    self.lat, self.lon = lat, lon
                self.refresh()
                return True, self.city
            return False, "City not found"
        except Exception as e:
            return False, str(e)

    def refresh(self):
        self.force_update = True
        self._wake.set()

    def get_weather_icon(self, code):
        mapping = {
            0: "ph.sun",
            1: "ph.cloud-sun", 2: "ph.cloud-sun", 3: "ph.cloud",
            45: "ph.cloud-fog", 48: "ph.cloud-fog",
            51: "ph.cloud-rain", 53: "ph.cloud-rain", 55: "ph.cloud-rain",
            61: "ph.cloud-rain", 63: "ph.cloud-rain", 65: "ph.cloud-rain",
            71: "ph.snowflake", 73: "ph.snowflake", 75: "ph.snowflake",
            80: "ph.cloud-rain", 81: "ph.cloud-rain", 82: "ph.cloud-rain",
            95: "ph.cloud-lightning", 96: "ph.cloud-lightning", 99: "ph.cloud-lightning"
        }
        return mapping.get(code, "ph.cloud")

    def get_weather_desc(self, code):
        mapping = {
            0: "Clear Sky",
            1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing Rime Fog",
            51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
            61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
            71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
            80: "Slight Rain Showers", 81: "Moderate Rain Showers", 82: "Violent Rain Showers",
            95: "Thunderstorm", 96: "Thunderstorm with Slight Hail", 99: "Thunderstorm with Heavy Hail"
        }
        return mapping.get(code, "Unknown")

    def run(self):
        next_update = 0.0
        while self.running:
            self._wake.clear()
            with self._location_lock:
                pending, self._pending_location = self._pending_location, None
            if pending:
                generation, city = pending
                success, message = self._set_location(city, generation)
                with self._location_lock:
                    current = generation == self._location_generation
                if self.running and current:
                    self.location_updated.emit(success, message)
            if not self.running:
                break
            if time.monotonic() >= next_update or self.force_update:
                self.force_update = False
                delay = 60
                try:
                    res = self._request_json("https://api.open-meteo.com/v1/forecast",
                        {"latitude": self.lat, "longitude": self.lon, "current_weather": "true",
                         "hourly": "temperature_2m,weathercode", "timezone": "auto"})
                    
                    if "current_weather" in res:
                        current = res["current_weather"]
                        hourly = res["hourly"]
                        
                                                            
                        hourly_data = []
                        current_time_str = current["time"][:13] + ":00"
                        try:
                            start_idx = hourly["time"].index(current_time_str)
                        except ValueError:
                            start_idx = 0
                            
                        for i in range(1, 6):
                            idx = start_idx + i
                            if idx < len(hourly["time"]):
                                t_str = hourly["time"][idx]
                                t_dt = datetime.datetime.strptime(t_str, "%Y-%m-%dT%H:%M")
                                hourly_data.append({
                                    "time": t_dt.strftime("%I%p").lstrip("0"),
                                    "temp": f"{int(hourly['temperature_2m'][idx])}°",
                                    "icon": self.get_weather_icon(hourly["weathercode"][idx])
                                })
                        
                        data = {
                            "city": self.city,
                            "temp": f"{int(current['temperature'])}°",
                            "desc": self.get_weather_desc(current["weathercode"]),
                            "icon": self.get_weather_icon(current["weathercode"]),
                            "hourly": hourly_data
                        }
                        if self.running:
                            self.weather_updated.emit(data)
                        delay = self.update_interval
                except Exception as e:
                    if self.running:
                        print(f"Weather update error: {e}")
                next_update = time.monotonic() + delay
            self._wake.wait(max(0, next_update - time.monotonic()))

    def stop(self):
        self.running = False
        self._stop_event.set()
        self._wake.set()
        return self.wait(1000)
