import json
import unittest

import httpx
from fastapi.testclient import TestClient

from app.api.preferences import get_llm_client
from app.main import app
from app.services.ai.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMRequestError,
)


class FakeLLMClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""

    async def complete_json(
        self, *, system_prompt: str, user_prompt: str
    ) -> dict:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


class PreferenceAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.fake_llm = FakeLLMClient(
            {
                "status": "ok",
                "constraints": {
                    "hard_days_off": ["TUESDAY"],
                    "hard_time_rules": [],
                    "soft_days_off": [],
                    "avoid_times": [],
                    "per_course": [],
                    "weights": {"compact_days": 2, "avoid_gaps": 3},
                },
                "issues": [],
            }
        )
        app.dependency_overrides[get_llm_client] = lambda: self.fake_llm

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.client.close()

    def test_parse_preferences_returns_validated_constraints(self) -> None:
        response = self.client.post(
            "/api/parse-preferences",
            json={"text": "Nghỉ thứ 3"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["constraints"]["hard_days_off"], ["TUESDAY"]
        )
        self.assertIn("Nghỉ thứ 3", self.fake_llm.user_prompt)

    def test_hard_period_prohibition_uses_hard_time_rule(self) -> None:
        self.fake_llm.response["constraints"]["hard_time_rules"] = [
            {
                "mode": "avoid",
                "target": {
                    "days": [],
                    "time_range": {
                        "unit": "period",
                        "start": 1,
                        "end": 1,
                    },
                },
            }
        ]
        response = self.client.post(
            "/api/parse-preferences",
            json={"text": "Không học tiết 1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["constraints"]["hard_time_rules"][0]["mode"], "avoid"
        )
        self.assertEqual(body["constraints"]["avoid_times"], [])

    def test_course_rule_is_removed_when_course_has_multiple_meetings(self) -> None:
        self.fake_llm.response["constraints"]["per_course"] = [
            {
                "course_id": "CS101",
                "mode": "prefer",
                "strength": "hard",
                "target": {
                    "days": ["WEDNESDAY"],
                    "time_range": {
                        "unit": "period",
                        "start": 2,
                        "end": 2,
                    },
                },
            }
        ]
        response = self.client.post(
            "/api/parse-preferences",
            json={
                "text": "Môn lập trình học tiết 2 thứ tư",
                "selected_courses": [
                    {
                        "course_id": "CS101",
                        "course_name": "Lập trình",
                        "weekly_meeting_count": 2,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "needs_clarification")
        self.assertEqual(body["constraints"]["per_course"], [])
        self.assertEqual(body["issues"][0]["code"], "UNSUPPORTED")

    def test_course_rule_is_kept_for_single_weekly_meeting(self) -> None:
        self.fake_llm.response["constraints"]["per_course"] = [
            {
                "course_id": "CS101",
                "mode": "prefer",
                "strength": "hard",
                "target": {
                    "days": ["WEDNESDAY"],
                    "time_range": {
                        "unit": "period",
                        "start": 2,
                        "end": 2,
                    },
                },
            }
        ]
        response = self.client.post(
            "/api/parse-preferences",
            json={
                "text": "Môn lập trình học tiết 2 thứ tư",
                "selected_courses": [
                    {
                        "course_id": "CS101",
                        "course_name": "Lập trình",
                        "weekly_meeting_count": 1,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(
            body["constraints"]["per_course"][0]["course_id"], "CS101"
        )

    def test_blank_text_is_rejected(self) -> None:
        response = self.client.post(
            "/api/parse-preferences",
            json={"text": "   "},
        )

        self.assertEqual(response.status_code, 422)

    def test_missing_llm_key_returns_service_unavailable(self) -> None:
        app.dependency_overrides[get_llm_client] = lambda: LLMClient(api_key="")
        response = self.client.post(
            "/api/parse-preferences",
            json={"text": "Nghỉ thứ 3"},
        )

        self.assertEqual(response.status_code, 503)


class LLMClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_json_uses_openai_compatible_chat_api(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(
                json.loads(request.content)["response_format"]["type"],
                "json_object",
            )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"ok": true}'}}]},
            )

        client = LLMClient(
            api_key="test-key",
            base_url="https://llm.example/v1",
            transport=httpx.MockTransport(handler),
        )

        result = await client.complete_json(
            system_prompt="system",
            user_prompt="user",
        )

        self.assertEqual(result, {"ok": True})

    async def test_missing_key_and_invalid_provider_status_are_explicit(self) -> None:
        missing_key_client = LLMClient(api_key="")
        with self.assertRaises(LLMConfigurationError):
            await missing_key_client.complete_json(
                system_prompt="system",
                user_prompt="user",
            )

        async def error_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        rate_limited_client = LLMClient(
            api_key="test-key",
            transport=httpx.MockTransport(error_handler),
        )
        with self.assertRaises(LLMRequestError):
            await rate_limited_client.complete_json(
                system_prompt="system",
                user_prompt="user",
            )


if __name__ == "__main__":
    unittest.main()
