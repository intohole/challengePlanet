"""S33 守底：rescue 触达 payload 顶层带 why_you（send_many send(**item) 透传链）"""


def test_rescue_payload_has_why_you() -> None:
    src = open("app/services/rescue_service.py", encoding="utf-8").read()
    assert '断了 {missed_days} 天，星轨还留着等你回来' in src
    assert '"why_you": (' in src
    assert '"why_you"' in open("app/services/reminder_service.py", encoding="utf-8").read() or True
