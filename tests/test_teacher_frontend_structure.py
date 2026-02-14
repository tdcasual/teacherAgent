"""Maintainability guardrails for teacher frontend structure."""

from pathlib import Path

_TEACHER_APP_PATH = (
    Path(__file__).resolve().parent.parent / "frontend" / "apps" / "teacher" / "src" / "App.tsx"
)
_TEACHER_SESSION_RAIL_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "chat"
    / "TeacherSessionRail.tsx"
)
_TEACHER_TOPBAR_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "layout"
    / "TeacherTopbar.tsx"
)
_TEACHER_PERSONA_MANAGER_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "persona"
    / "TeacherPersonaManager.tsx"
)
_TEACHER_ROUTING_PAGE_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingPage.tsx"
)
_TEACHER_ROUTING_SIM_SECTION_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingSimulateSection.tsx"
)
_TEACHER_ROUTING_HISTORY_SECTION_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingHistorySection.tsx"
)
_TEACHER_ROUTING_PROVIDERS_SECTION_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingProvidersSection.tsx"
)
_TEACHER_ROUTING_RULES_SECTION_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingRulesSection.tsx"
)
_TEACHER_ROUTING_CHANNELS_SECTION_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "RoutingChannelsSection.tsx"
)
_TEACHER_ROUTING_OVERVIEW_SYNC_HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "useRoutingOverviewSync.ts"
)
_TEACHER_ROUTING_PROVIDER_MUTATIONS_HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "useRoutingProviderMutations.ts"
)
_TEACHER_ROUTING_DRAFT_ACTIONS_HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "routing"
    / "useRoutingDraftActions.ts"
)


def test_teacher_app_line_budget() -> None:
    lines = _TEACHER_APP_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 800, (
        f"teacher App.tsx is {line_count} lines (limit 800). "
        "Extract sidebar/ui-panel derivations into focused hooks."
    )


def test_teacher_session_rail_extracted() -> None:
    assert _TEACHER_SESSION_RAIL_PATH.exists(), (
        "Teacher session rail should be extracted into " "features/chat/TeacherSessionRail.tsx."
    )
    app_source = _TEACHER_APP_PATH.read_text(encoding="utf-8")
    assert "TeacherSessionRail" in app_source
    assert "<TeacherSessionRail" in app_source
    assert "<SessionSidebar" not in app_source, "App.tsx should not render SessionSidebar directly."


def test_teacher_topbar_has_persona_manager_entry() -> None:
    source = _TEACHER_TOPBAR_PATH.read_text(encoding="utf-8")
    assert "角色管理" in source
    assert "onOpenPersonaManager" in source


def test_teacher_persona_manager_component_exists_and_is_mounted() -> None:
    assert _TEACHER_PERSONA_MANAGER_PATH.exists(), (
        "Teacher persona manager should be implemented at "
        "features/persona/TeacherPersonaManager.tsx."
    )
    app_source = _TEACHER_APP_PATH.read_text(encoding="utf-8")
    assert "TeacherPersonaManager" in app_source
    assert "<TeacherPersonaManager" in app_source


def test_teacher_routing_page_line_budget() -> None:
    lines = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 780, (
        f"teacher RoutingPage.tsx is {line_count} lines (limit 780). "
        "Split routing sections into focused sub-components and hooks."
    )


def test_teacher_routing_simulate_and_history_sections_are_extracted() -> None:
    assert _TEACHER_ROUTING_SIM_SECTION_PATH.exists(), (
        "Routing simulate section should be extracted into "
        "features/routing/RoutingSimulateSection.tsx."
    )
    assert _TEACHER_ROUTING_HISTORY_SECTION_PATH.exists(), (
        "Routing history section should be extracted into "
        "features/routing/RoutingHistorySection.tsx."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "RoutingSimulateSection" in source
    assert "<RoutingSimulateSection" in source
    assert "RoutingHistorySection" in source
    assert "<RoutingHistorySection" in source


def test_teacher_routing_providers_and_rules_sections_are_extracted() -> None:
    assert _TEACHER_ROUTING_PROVIDERS_SECTION_PATH.exists(), (
        "Routing providers section should be extracted into "
        "features/routing/RoutingProvidersSection.tsx."
    )
    assert _TEACHER_ROUTING_RULES_SECTION_PATH.exists(), (
        "Routing rules section should be extracted into "
        "features/routing/RoutingRulesSection.tsx."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "RoutingProvidersSection" in source
    assert "<RoutingProvidersSection" in source
    assert "RoutingRulesSection" in source
    assert "<RoutingRulesSection" in source


def test_teacher_routing_channels_section_is_extracted() -> None:
    assert _TEACHER_ROUTING_CHANNELS_SECTION_PATH.exists(), (
        "Routing channels section should be extracted into "
        "features/routing/RoutingChannelsSection.tsx."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "RoutingChannelsSection" in source
    assert "<RoutingChannelsSection" in source


def test_teacher_routing_overview_sync_hook_is_extracted() -> None:
    assert _TEACHER_ROUTING_OVERVIEW_SYNC_HOOK_PATH.exists(), (
        "Routing overview sync logic should be extracted into "
        "features/routing/useRoutingOverviewSync.ts."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "useRoutingOverviewSync" in source
    assert "useRoutingOverviewSync(" in source


def test_teacher_routing_provider_mutations_hook_is_extracted() -> None:
    assert _TEACHER_ROUTING_PROVIDER_MUTATIONS_HOOK_PATH.exists(), (
        "Routing provider mutation logic should be extracted into "
        "features/routing/useRoutingProviderMutations.ts."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "useRoutingProviderMutations" in source
    assert "useRoutingProviderMutations(" in source


def test_teacher_routing_draft_actions_hook_is_extracted() -> None:
    assert _TEACHER_ROUTING_DRAFT_ACTIONS_HOOK_PATH.exists(), (
        "Routing draft action logic should be extracted into "
        "features/routing/useRoutingDraftActions.ts."
    )
    source = _TEACHER_ROUTING_PAGE_PATH.read_text(encoding="utf-8")
    assert "useRoutingDraftActions" in source
    assert "useRoutingDraftActions(" in source
