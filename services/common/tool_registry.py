from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

JsonSchema = Dict[str, Any]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: JsonSchema
    mutating: bool = False

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_mcp(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
        }


class ToolRegistry:
    def __init__(self, tools: Dict[str, ToolDef]):
        self._tools = dict(tools)

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def require(self, name: str) -> ToolDef:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"tool not found: {name}")
        return tool

    def openai_tools(self, names: Iterable[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for n in names:
            tool = self.get(n)
            if tool is None:
                continue
            out.append(tool.to_openai())
        return out

    def mcp_tools(self, names: Iterable[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for n in names:
            tool = self.get(n)
            if tool is None:
                continue
            out.append(tool.to_mcp())
        return out

    def validate_arguments(self, name: str, args: Any) -> List[str]:
        tool = self.get(name)
        if tool is None:
            return [f"unknown tool: {name}"]
        if args is None:
            args = {}
        issues: List[str] = []
        _validate_schema(tool.parameters, args, path="arguments", issues=issues)
        return issues


def _schema_object(
    properties: Dict[str, Any],
    required: Optional[List[str]] = None,
    *,
    additional_properties: bool = False,
) -> JsonSchema:
    schema: JsonSchema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": bool(additional_properties),
    }
    if required:
        schema["required"] = list(required)
    return schema


def _validate_schema(schema: Dict[str, Any], value: Any, path: str, issues: List[str]) -> None:
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(value, dict):
            issues.append(f"{path}: expected object")
            return
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                key_text = str(key).strip()
                if key_text and key_text not in value:
                    issues.append(f"{path}.{key_text}: required")
        additional_allowed = schema.get("additionalProperties", True)
        if additional_allowed is False:
            allowed_keys = set(properties.keys())
            for key in value.keys():
                if key not in allowed_keys:
                    issues.append(f"{path}.{key}: unexpected")
        for key, subschema in properties.items():
            if key not in value:
                continue
            if not isinstance(subschema, dict):
                continue
            _validate_schema(subschema, value[key], f"{path}.{key}", issues)
        return

    if schema_type == "array":
        if not isinstance(value, list):
            issues.append(f"{path}: expected array")
            return
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate_schema(item_schema, item, f"{path}[{idx}]", issues)
        return

    if schema_type == "string":
        if not isinstance(value, str):
            issues.append(f"{path}: expected string")
            return
    elif schema_type == "integer":
        if not (isinstance(value, int) and not isinstance(value, bool)):
            issues.append(f"{path}: expected integer")
            return
    elif schema_type == "number":
        if not (
            (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        ):
            issues.append(f"{path}: expected number")
            return
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            issues.append(f"{path}: expected boolean")
            return

    enum = schema.get("enum")
    if isinstance(enum, list) and enum and value not in enum:
        issues.append(f"{path}: expected one of {enum}")


def build_default_registry() -> ToolRegistry:
    tools: Dict[str, ToolDef] = {}

    # Assignments & lessons
    tools["assignment.list"] = ToolDef(
        name="assignment.list",
        description="List available assignments",
        parameters=_schema_object({}),
    )
    tools["assignment.generate"] = ToolDef(
        name="assignment.generate",
        mutating=True,
        description="Generate assignment questions from KP / explicit ids / core examples",
        parameters=_schema_object(
            {
                "assignment_id": {"type": "string"},
                "kp": {"type": "string"},
                "question_ids": {"type": "string"},
                "per_kp": {"type": "integer", "default": 5},
                "core_examples": {"type": "string"},
                "generate": {"type": "boolean", "default": False},
                "mode": {"type": "string"},
                "date": {"type": "string"},
                "due_at": {"type": "string"},
                "subject_id": {
                    "type": "string",
                    "description": "opaque subject id: physics | math | generic",
                },
                "class_name": {"type": "string"},
                "student_ids": {"type": "string"},
                "source": {"type": "string"},
                "requirements": {"type": "object"},
            },
            required=["assignment_id", "subject_id"],
        ),
    )
    tools["assignment.requirements.save"] = ToolDef(
        name="assignment.requirements.save",
        mutating=True,
        description="Save assignment requirements (8-item teacher checklist)",
        parameters=_schema_object(
            {
                "assignment_id": {"type": "string"},
                "date": {"type": "string"},
                "requirements": {"type": "object"},
            },
            required=["assignment_id", "requirements"],
        ),
    )
    tools["assignment.render"] = ToolDef(
        name="assignment.render",
        mutating=True,
        description="Render assignment PDF",
        parameters=_schema_object(
            {
                "assignment_id": {"type": "string"},
                "assignment_questions": {
                    "type": "string",
                    "description": "optional csv path override",
                },
                "out": {"type": "string", "description": "optional output pdf path"},
            },
            required=["assignment_id"],
        ),
    )
    tools["assignment.progress"] = ToolDef(
        name="assignment.progress",
        description="Get assignment progress (results and process columns)",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.missing"] = ToolDef(
        name="assignment.missing",
        description="List students who have not submitted an assignment",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.overdue"] = ToolDef(
        name="assignment.overdue",
        description="List students overdue and unsubmitted for an assignment",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.attempt.get"] = ToolDef(
        name="assignment.attempt.get",
        description="Get one student's attempt and official score for an assignment",
        parameters=_schema_object(
            {
                "assignment_id": {"type": "string"},
                "student_id": {"type": "string"},
            },
            required=["assignment_id", "student_id"],
        ),
    )
    tools["assignment.publish"] = ToolDef(
        name="assignment.publish",
        mutating=True,
        description="Publish a draft assignment (draft → published)",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.archive"] = ToolDef(
        name="assignment.archive",
        mutating=True,
        description="Archive a published assignment (today list excludes it immediately)",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.unarchive"] = ToolDef(
        name="assignment.unarchive",
        mutating=True,
        description="Unarchive an assignment (archived → published)",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.recompute_roster"] = ToolDef(
        name="assignment.recompute_roster",
        mutating=True,
        description="Overwrite expected_students from current enrollments",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["assignment.my_today"] = ToolDef(
        name="assignment.my_today",
        description="Student today assignment list (same source as HTTP today)",
        parameters=_schema_object({"date": {"type": "string"}}),
    )
    tools["assignment.my_result"] = ToolDef(
        name="assignment.my_result",
        description="Student official score and submission status for one assignment",
        parameters=_schema_object({"assignment_id": {"type": "string"}}, required=["assignment_id"]),
    )
    tools["lesson.list"] = ToolDef(
        name="lesson.list",
        description="List available lessons",
        parameters=_schema_object({}),
    )
    tools["lesson.capture"] = ToolDef(
        name="lesson.capture",
        mutating=True,
        description="Capture lesson materials (OCR + examples)",
        parameters=_schema_object(
            {
                "lesson_id": {"type": "string"},
                "topic": {"type": "string"},
                "class_name": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "discussion_notes": {"type": "string"},
                "lesson_plan": {"type": "string"},
                "force_ocr": {"type": "boolean", "default": False},
                "ocr_mode": {"type": "string", "default": "FREE_OCR"},
                "language": {"type": "string", "default": "zh"},
                "out_base": {"type": "string", "default": "data/lessons"},
            },
            required=["lesson_id", "topic", "sources"],
        ),
    )

    # Students
    tools["student.search"] = ToolDef(
        name="student.search",
        description="Search students by name or keyword",
        parameters=_schema_object(
            {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
            required=["query"],
        ),
    )
    tools["student.profile.get"] = ToolDef(
        name="student.profile.get",
        description="Get student profile JSON",
        parameters=_schema_object({"student_id": {"type": "string"}}, required=["student_id"]),
    )
    tools["student.profile.update"] = ToolDef(
        name="student.profile.update",
        mutating=True,
        description="Update derived fields in student profile",
        parameters=_schema_object(
            {
                "student_id": {"type": "string"},
                "weak_kp": {"type": "string"},
                "medium_kp": {"type": "string"},
                "strong_kp": {"type": "string"},
                "next_focus": {"type": "string"},
                "interaction_note": {"type": "string"},
            },
            required=["student_id"],
        ),
    )
    tools["student.import"] = ToolDef(
        name="student.import",
        mutating=True,
        description="Import students from scored response CSV into student_profiles",
        parameters=_schema_object(
            {
                "source": {
                    "type": "string",
                    "description": "responses_scored or responses",
                    "default": "responses_scored",
                },
                "file_path": {"type": "string", "description": "override responses csv path"},
                "mode": {"type": "string", "description": "merge or overwrite", "default": "merge"},
            }
        ),
    )

    # Core examples
    tools["core_example.search"] = ToolDef(
        name="core_example.search",
        description="Search core examples (from data/core_examples/examples.csv)",
        parameters=_schema_object({"kp_id": {"type": "string"}, "example_id": {"type": "string"}}),
    )
    tools["core_example.register"] = ToolDef(
        name="core_example.register",
        mutating=True,
        description="Register a core example into data/core_examples",
        parameters=_schema_object(
            {
                "example_id": {"type": "string"},
                "kp_id": {"type": "string"},
                "core_model": {"type": "string"},
                "difficulty": {"type": "string"},
                "source_ref": {"type": "string"},
                "tags": {"type": "string"},
                "stem_file": {"type": "string"},
                "solution_file": {"type": "string"},
                "model_file": {"type": "string"},
                "figure_file": {"type": "string"},
                "discussion_file": {"type": "string"},
                "variant_file": {"type": "string"},
                "from_lesson": {"type": "string"},
                "lesson_example_id": {"type": "string"},
                "lesson_figure": {"type": "string"},
            },
            required=["example_id", "kp_id", "core_model"],
        ),
    )
    tools["core_example.render"] = ToolDef(
        name="core_example.render",
        description="Render core example PDF",
        parameters=_schema_object(
            {"example_id": {"type": "string"}, "out": {"type": "string"}}, required=["example_id"]
        ),
    )

    # Charts / code execution (teacher-only in API role gate)
    tools["chart.exec"] = ToolDef(
        name="chart.exec",
        mutating=True,
        description=(
            "Execute Python code and return generated artifacts. "
            "Helpers available in code: save_chart(name), save_text(name, content), "
            "save_file(path_or_name, content=None) — copies/creates file in OUTPUT_DIR. "
            "Files written to cwd are also auto-captured. "
            "Result includes artifacts_markdown — paste it directly into your reply "
            "to show image previews and download links to the user."
        ),
        parameters=_schema_object(
            {
                "python_code": {
                    "type": "string",
                    "description": "Python code to execute. Use save_file(path) to save output files.",
                },
                "input_data": {
                    "type": "object",
                    "description": "optional JSON object passed to python as input_data",
                },
                "chart_hint": {"type": "string", "description": "optional intent/notes"},
                "timeout_sec": {"type": "integer", "default": 120},
                "save_as": {
                    "type": "string",
                    "description": "optional PNG filename, e.g. main.png",
                },
                "auto_install": {"type": "boolean", "default": False},
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "optional pip packages to install",
                },
                "max_retries": {"type": "integer", "default": 1},
            },
            required=["python_code"],
        ),
    )
    tools["chart.agent.run"] = ToolDef(
        name="chart.agent.run",
        mutating=True,
        description="Generate chart code with LLM, auto-install dependencies, execute, and auto-repair on failures",
        parameters=_schema_object(
            {
                "task": {"type": "string", "description": "chart requirement in natural language"},
                "input_data": {"type": "object", "description": "optional structured input data"},
                "title": {
                    "type": "string",
                    "description": "optional markdown title for rendered image",
                },
                "engine": {"type": "string", "description": "llm(default)|auto"},
                "chart_hint": {"type": "string"},
                "save_as": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 180},
                "max_retries": {"type": "integer", "default": 3},
                "auto_install": {"type": "boolean", "default": True},
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "optional pip package hints",
                },
                "opencode_enabled": {"type": "boolean"},
                "opencode_bin": {"type": "string"},
                "opencode_mode": {"type": "string", "description": "run|attach"},
                "opencode_attach_url": {"type": "string"},
                "opencode_agent": {"type": "string"},
                "opencode_model": {"type": "string"},
                "opencode_config_path": {"type": "string"},
                "opencode_timeout_sec": {"type": "integer"},
                "opencode_max_retries": {"type": "integer"},
            },
            required=["task"],
        ),
    )

    # Teacher workspace/memory (API-only for now, but defined here to keep one source of truth)
    tools["teacher.workspace.init"] = ToolDef(
        name="teacher.workspace.init",
        description="Initialize teacher workspace files (AGENTS/USER/MEMORY/etc.)",
        parameters=_schema_object(
            {"teacher_id": {"type": "string", "description": "optional teacher id"}}
        ),
    )
    tools["teacher.memory.get"] = ToolDef(
        name="teacher.memory.get",
        description="Read teacher workspace memory/profile files (safe subset)",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "file": {
                    "type": "string",
                    "description": "MEMORY.md/USER.md/AGENTS.md/SOUL.md/HEARTBEAT.md or DAILY",
                },
                "date": {"type": "string", "description": "used when file=DAILY"},
                "max_chars": {"type": "integer", "default": 8000},
            }
        ),
    )
    tools["teacher.memory.search"] = ToolDef(
        name="teacher.memory.search",
        description="Search teacher memory/workspace files for a keyword",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            required=["query"],
        ),
    )
    tools["teacher.memory.propose"] = ToolDef(
        name="teacher.memory.propose",
        description="Propose a memory/workspace update and return proposal_id for review",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "target": {
                    "type": "string",
                    "description": "MEMORY|DAILY|USER|AGENTS|SOUL|HEARTBEAT",
                    "default": "MEMORY",
                },
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            required=["content"],
        ),
    )
    tools["teacher.memory.apply"] = ToolDef(
        name="teacher.memory.apply",
        mutating=True,
        description="Apply or reject a proposed memory update",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "proposal_id": {"type": "string"},
                "approve": {"type": "boolean", "default": True},
            },
            required=["proposal_id"],
        ),
    )
    return ToolRegistry(tools)


DEFAULT_TOOL_REGISTRY = build_default_registry()
