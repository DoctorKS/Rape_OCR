import unittest

from rape_ocr.api import create_app


class ApiTest(unittest.TestCase):
    def test_create_app_exposes_health_route(self):
        app = create_app(data_dir=None, prefer_paddle=False)
        health_route = next(route for route in app.routes if getattr(route, "path", None) == "/health")
        response = health_route.endpoint()

        self.assertEqual(response["status"], "ok")
        self.assertTrue(response["offline"])
