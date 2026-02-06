from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


JsonSchema = Dict[str, Any]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: JsonSchema

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
        if not ((isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)):
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

    # Exam tools
    tools["exam.list"] = ToolDef(
        name="exam.list",
        description="List available exams",
        parameters=_schema_object({}),
    )
    tools["exam.get"] = ToolDef(
        name="exam.get",
        description="Get exam manifest + summary by exam_id",
        parameters=_schema_object({"exam_id": {"type": "string"}}, required=["exam_id"]),
    )
    tools["exam.analysis.get"] = ToolDef(
        name="exam.analysis.get",
        description="Get exam draft analysis (or compute minimal summary if missing)",
        parameters=_schema_object({"exam_id": {"type": "string"}}, required=["exam_id"]),
    )
    tools["exam.analysis.charts.generate"] = ToolDef(
        name="exam.analysis.charts.generate",
        description="One-click generate exam analysis charts and Markdown image output",
        parameters=_schema_object(
            {
                "exam_id": {"type": "string"},
                "chart_types": {
                    "type": "array",
                    "description": "optional chart list: score_distribution/knowledge_radar/class_compare/question_discrimination",
                    "items": {"type": "string"},
                },
                "top_n": {"type": "integer", "default": 12},
                "timeout_sec": {"type": "integer", "default": 120},
            },
            required=["exam_id"],
        ),
    )
    tools["exam.students.list"] = ToolDef(
        name="exam.students.list",
        description="List students in an exam with total scores and ranks",
        parameters=_schema_object(
            {"exam_id": {"type": "string"}, "limit": {"type": "integer", "default": 50}},
            required=["exam_id"],
        ),
    )
    tools["exam.student.get"] = ToolDef(
        name="exam.student.get",
        description="Get one student's per-question breakdown within an exam",
        parameters=_schema_object(
            {
                "exam_id": {"type": "string"},
                "student_id": {"type": "string"},
                "student_name": {"type": "string"},
                "class_name": {"type": "string"},
            },
            required=["exam_id"],
        ),
    )
    tools["exam.question.get"] = ToolDef(
        name="exam.question.get",
        description="Get one question's score distribution and stats within an exam",
        parameters=_schema_object(
            {
                "exam_id": {"type": "string"},
                "question_id": {"type": "string"},
                "question_no": {"type": "string"},
            },
            required=["exam_id"],
        ),
    )

    # Assignments & lessons
    tools["assignment.list"] = ToolDef(
        name="assignment.list",
        description="List available assignments",
        parameters=_schema_object({}),
    )
    tools["assignment.generate"] = ToolDef(
        name="assignment.generate",
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
                "class_name": {"type": "string"},
                "student_ids": {"type": "string"},
                "source": {"type": "string"},
                "requirements": {"type": "object"},
            },
            required=["assignment_id"],
        ),
    )
    tools["assignment.requirements.save"] = ToolDef(
        name="assignment.requirements.save",
        description="Save assignment requirements (8-item teacher checklist)",
        parameters=_schema_object(
            {"assignment_id": {"type": "string"}, "date": {"type": "string"}, "requirements": {"type": "object"}},
            required=["assignment_id", "requirements"],
        ),
    )
    tools["assignment.render"] = ToolDef(
        name="assignment.render",
        description="Render assignment PDF",
        parameters=_schema_object(
            {
                "assignment_id": {"type": "string"},
                "assignment_questions": {"type": "string", "description": "optional csv path override"},
                "out": {"type": "string", "description": "optional output pdf path"},
            },
            required=["assignment_id"],
        ),
    )
    tools["lesson.list"] = ToolDef(
        name="lesson.list",
        description="List available lessons",
        parameters=_schema_object({}),
    )
    tools["lesson.capture"] = ToolDef(
        name="lesson.capture",
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
        parameters=_schema_object({"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}}, required=["query"]),
    )
    tools["student.profile.get"] = ToolDef(
        name="student.profile.get",
        description="Get student profile JSON",
        parameters=_schema_object({"student_id": {"type": "string"}}, required=["student_id"]),
    )
    tools["student.profile.update"] = ToolDef(
        name="student.profile.update",
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
        description="Import students from exam responses into student_profiles",
        parameters=_schema_object(
            {
                "source": {"type": "string", "description": "responses_scored or responses", "default": "responses_scored"},
                "exam_id": {"type": "string", "description": "exam id to locate manifest"},
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
        parameters=_schema_object({"example_id": {"type": "string"}, "out": {"type": "string"}}, required=["example_id"]),
    )

    # Charts (teacher-only in API role gate)
    tools["chart.exec"] = ToolDef(
        name="chart.exec",
        description="Execute Python chart code and return generated image URL/artifacts",
        parameters=_schema_object(
            {
                "python_code": {"type": "string", "description": "Python code to execute"},
                "input_data": {"type": "object", "description": "optional JSON object passed to python as input_data"},
                "chart_hint": {"type": "string", "description": "optional chart intent/notes"},
                "timeout_sec": {"type": "integer", "default": 120},
                "save_as": {"type": "string", "description": "optional PNG filename, e.g. main.png"},
                "auto_install": {"type": "boolean", "default": False},
                "packages": {"type": "array", "items": {"type": "string"}, "description": "optional pip packages to install"},
                "max_retries": {"type": "integer", "default": 1},
            },
            required=["python_code"],
        ),
    )
    tools["chart.agent.run"] = ToolDef(
        name="chart.agent.run",
        description="Generate chart code with LLM, auto-install dependencies, execute, and auto-repair on failures",
        parameters=_schema_object(
            {
                "task": {"type": "string", "description": "chart requirement in natural language"},
                "input_data": {"type": "object", "description": "optional structured input data"},
                "title": {"type": "string", "description": "optional markdown title for rendered image"},
                "engine": {"type": "string", "description": "auto|opencode|llm"},
                "chart_hint": {"type": "string"},
                "save_as": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 180},
                "max_retries": {"type": "integer", "default": 3},
                "auto_install": {"type": "boolean", "default": True},
                "packages": {"type": "array", "items": {"type": "string"}, "description": "optional pip package hints"},
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
        parameters=_schema_object({"teacher_id": {"type": "string", "description": "optional teacher id"}}),
    )
    tools["teacher.memory.get"] = ToolDef(
        name="teacher.memory.get",
        description="Read teacher workspace memory/profile files (safe subset)",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "file": {"type": "string", "description": "MEMORY.md/USER.md/AGENTS.md/SOUL.md/HEARTBEAT.md or DAILY"},
                "date": {"type": "string", "description": "used when file=DAILY"},
                "max_chars": {"type": "integer", "default": 8000},
            }
        ),
    )
    tools["teacher.memory.search"] = ToolDef(
        name="teacher.memory.search",
        description="Search teacher memory/workspace files for a keyword",
        parameters=_schema_object(
            {"teacher_id": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
            required=["query"],
        ),
    )
    tools["teacher.memory.propose"] = ToolDef(
        name="teacher.memory.propose",
        description="Propose a memory/workspace update and return proposal_id for review",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "target": {"type": "string", "description": "MEMORY|DAILY|USER|AGENTS|SOUL|HEARTBEAT", "default": "MEMORY"},
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            required=["content"],
        ),
    )
    tools["teacher.memory.apply"] = ToolDef(
        name="teacher.memory.apply",
        description="Apply or reject a proposed memory update",
        parameters=_schema_object(
            {"teacher_id": {"type": "string"}, "proposal_id": {"type": "string"}, "approve": {"type": "boolean", "default": True}},
            required=["proposal_id"],
        ),
    )
    tools["teacher.llm_routing.get"] = ToolDef(
        name="teacher.llm_routing.get",
        description="Get current LLM routing config, validation result, proposals, and history",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "history_limit": {"type": "integer", "default": 20},
                "proposal_limit": {"type": "integer", "default": 20},
                "proposal_status": {"type": "string", "description": "optional filter: pending/applied/rejected/failed"},
            }
        ),
    )
    tools["teacher.llm_routing.simulate"] = ToolDef(
        name="teacher.llm_routing.simulate",
        description="Simulate which channel/model would be selected for a task context",
        parameters=_schema_object(
            {
                "role": {"type": "string", "default": "teacher"},
                "skill_id": {"type": "string"},
                "kind": {"type": "string", "description": "task kind, e.g. chat.agent"},
                "needs_tools": {"type": "boolean", "default": False},
                "needs_json": {"type": "boolean", "default": False},
            }
        ),
    )
    tools["teacher.llm_routing.propose"] = ToolDef(
        name="teacher.llm_routing.propose",
        description="Create a pending proposal for routing config change",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "note": {"type": "string"},
                "config": {"type": "object"},
            },
            required=["config"],
        ),
    )
    tools["teacher.llm_routing.apply"] = ToolDef(
        name="teacher.llm_routing.apply",
        description="Apply or reject a routing proposal by proposal_id",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "proposal_id": {"type": "string"},
                "approve": {"type": "boolean", "default": True},
            },
            required=["proposal_id"],
        ),
    )
    tools["teacher.llm_routing.rollback"] = ToolDef(
        name="teacher.llm_routing.rollback",
        description="Rollback routing config to an old version snapshot",
        parameters=_schema_object(
            {
                "teacher_id": {"type": "string"},
                "target_version": {"type": "integer"},
                "note": {"type": "string"},
            },
            required=["target_version"],
        ),
    )

    return ToolRegistry(tools)


DEFAULT_TOOL_REGISTRY = build_default_registry()
