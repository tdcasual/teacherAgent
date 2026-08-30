from __future__ import annotations

from pathlib import Path

HOWTO_PATH = Path("docs/how-to/student-login-and-submit.md")
LOGIN_UI_PATH = Path("frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx")
HOME_UI_PATH = Path("frontend/apps/student/src/features/layout/StudentTopbar.tsx")
COMPOSER_UI_PATH = Path("frontend/apps/student/src/features/chat/ChatComposer.tsx")
TODAY_HOME_UI_PATH = Path("frontend/apps/student/src/features/home/StudentTodayHome.tsx")
SUBMIT_UI_PATH = Path("frontend/apps/student/src/features/submit/StudentSubmitPanel.tsx")
HISTORY_UI_PATH = Path("frontend/apps/student/src/features/history/StudentAssignmentHistoryPage.tsx")
SECURITY_PATH = Path("SECURITY.md")

FAKE_SUBMIT_UI_PHRASES = (
    "打开作业提交入口",
    "作业提交入口",
    "drop-zone",
    "dropzone",
    "Dropzone",
    "拖放区",
)


def test_student_howto_matches_chat_home_ui() -> None:
    howto = HOWTO_PATH.read_text(encoding="utf-8")
    login_ui = LOGIN_UI_PATH.read_text(encoding="utf-8")
    home_ui = HOME_UI_PATH.read_text(encoding="utf-8")
    composer_ui = COMPOSER_UI_PATH.read_text(encoding="utf-8")
    today_home_ui = TODAY_HOME_UI_PATH.read_text(encoding="utf-8")
    submit_ui = SUBMIT_UI_PATH.read_text(encoding="utf-8")
    history_ui = HISTORY_UI_PATH.read_text(encoding="utf-8")

    assert "姓名" in login_ui
    assert "班级" in login_ui
    assert "密码" in login_ui
    assert "今日任务" in home_ui
    assert 'type="file"' in composer_ui
    assert "student-today-home" in today_home_ui
    assert "提交作业" in today_home_ui
    assert "student-submit-panel" in submit_ui
    assert "作业记录" in history_ui

    assert "姓名" in howto
    assert "班级" in howto
    assert "密码" in howto
    assert "今日任务" in howto
    assert "聊天" in howto
    assert "附件" in howto
    assert "提交作业" in howto
    assert "作业记录" in howto
    assert "对话不会记为提交" in howto
    assert "/student/submit" in howto
    for phrase in FAKE_SUBMIT_UI_PHRASES:
        assert phrase not in howto, f"how-to still describes fake submit UI: {phrase}"


def test_security_md_has_github_advisory_contact() -> None:
    text = SECURITY_PATH.read_text(encoding="utf-8")
    assert "GitHub Security Advisory" in text
    assert "security/advisories" in text
