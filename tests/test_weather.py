import threading
import time
import unittest
from unittest.mock import patch

import requests
from PyQt6.QtCore import Qt

from weather_monitor import WeatherMonitor


class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class WeatherTests(unittest.TestCase):
    def test_location_request_returns_before_network_completes(self):
        monitor = WeatherMonitor()
        self.assertTrue(callable(getattr(monitor, "request_location", None)),
                        "UI needs a nonblocking location request")
        entered, release, received = (threading.Event() for _ in range(3))
        result = []

        def network(url, **kwargs):
            if "geocoding" in url:
                entered.set()
                release.wait(2)
                return Response({"results": [{"name": "New Delhi", "country": "India",
                                              "latitude": 28.6, "longitude": 77.2}]})
            raise requests.ConnectionError("offline forecast")

        def completed(ok, message):
            result.append((ok, message))
            received.set()

        monitor.location_updated.connect(completed, Qt.ConnectionType.DirectConnection)
        with patch("weather_monitor.requests.get", side_effect=network):
            started = time.monotonic()
            monitor.request_location("New Delhi")
            self.assertLess(time.monotonic() - started, .1)
            monitor.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(monitor.city, "Varanasi, India")
                release.set()
                self.assertTrue(received.wait(1))
                self.assertEqual(result, [(True, "New Delhi, India")])
                self.assertEqual((monitor.lat, monitor.lon), (28.6, 77.2))
            finally:
                release.set()
                monitor.stop()

    def test_failed_forecast_does_not_retry_each_second(self):
        monitor = WeatherMonitor()
        called = threading.Event()
        count = []

        def network(*args, **kwargs):
            count.append(1)
            called.set()
            raise requests.ConnectionError("offline")

        with patch("weather_monitor.requests.get", side_effect=network):
            monitor.start()
            try:
                self.assertTrue(called.wait(1))
                time.sleep(1.15)
                self.assertEqual(len(count), 1, "offline requests must back off")
            finally:
                monitor.stop()

    def test_stop_during_network_io_finishes_worker_promptly(self):
        monitor = WeatherMonitor()
        entered, release = threading.Event(), threading.Event()

        def network(*args, **kwargs):
            entered.set()
            release.wait(2)
            raise requests.ConnectionError("cancelled fixture")

        with patch("weather_monitor.requests.get", side_effect=network):
            monitor.start()
            self.assertTrue(entered.wait(1))
            watchdog = threading.Timer(.5, release.set)
            watchdog.start()
            try:
                started = time.monotonic()
                monitor.stop()
                self.assertLess(time.monotonic() - started, .25)
                self.assertFalse(monitor.isRunning())
            finally:
                release.set()
                watchdog.join()
                monitor.wait(2000)

    def test_empty_location_does_not_replace_existing_location(self):
        monitor = WeatherMonitor()
        with patch("weather_monitor.requests.get") as network:
            ok, _ = monitor.set_location("   ")
        self.assertFalse(ok)
        self.assertEqual(monitor.city, "Varanasi, India")
        self.assertFalse(network.called)

    def test_city_query_is_encoded_separately_from_url(self):
        monitor = WeatherMonitor()
        queries = []

        def network(url, **kwargs):
            queries.append((url, kwargs))
            return Response({"results": []})

        with patch("weather_monitor.requests.get", side_effect=network):
            ok, _ = monitor.set_location("A&B")
        self.assertFalse(ok)
        self.assertNotIn("A&B", queries[0][0])
        self.assertEqual(queries[0][1]["params"]["name"], "A&B")

    def test_forecast_starts_after_location_current_hour(self):
        monitor = WeatherMonitor()
        received = threading.Event()
        results, queries = [], []

        def network(url, **kwargs):
            queries.append(kwargs)
            return Response({"current_weather": {"time": "2026-10-20T04:25",
                "temperature": 20, "weathercode": 0}, "hourly": {
                "time": [f"2026-10-20T{hour:02}:00" for hour in range(2, 10)],
                "temperature_2m": [10, 11, 12, 13, 14, 15, 16, 17],
                "weathercode": [0] * 8}})

        def completed(data):
            results.append(data)
            received.set()

        monitor.weather_updated.connect(completed, Qt.ConnectionType.DirectConnection)
        with patch("weather_monitor.requests.get", side_effect=network):
            monitor.start()
            try:
                self.assertTrue(received.wait(1))
                self.assertEqual(results[0]["hourly"][0]["time"], "5AM")
                self.assertEqual(results[0]["hourly"][0]["temp"], "13°")
                self.assertEqual(queries[0]["params"].get("timezone"), "auto")
            finally:
                monitor.stop()

    def test_newer_location_suppresses_stale_lookup_result(self):
        monitor = WeatherMonitor()
        old_entered, release, received = (threading.Event() for _ in range(3))
        results = []

        def network(url, **kwargs):
            if "geocoding" not in url:
                raise requests.ConnectionError("offline forecast")
            city = kwargs["params"]["name"]
            if city == "Old":
                old_entered.set()
                release.wait(2)
            return Response({"results": [{"name": city, "country": "India",
                                          "latitude": 10, "longitude": 20}]})

        def completed(ok, text):
            results.append((ok, text))
            received.set()

        monitor.location_updated.connect(completed, Qt.ConnectionType.DirectConnection)
        monitor.request_location("Old")
        with patch("weather_monitor.requests.get", side_effect=network):
            monitor.start()
            try:
                self.assertTrue(old_entered.wait(1))
                monitor.request_location("New")
                release.set()
                self.assertTrue(received.wait(1))
                self.assertEqual(results, [(True, "New, India")])
                self.assertEqual(monitor.city, "New, India")
            finally:
                release.set()
                monitor.stop()


if __name__ == "__main__":
    unittest.main()
