作业流程（必须遵守）：
工作台先选择 assignment_kind，再选择 content_source（upload / bank / ai）。upload、题库选题、AI 起草都只写草稿，对学生不可见。
发布草稿：调用 POST /assignment/upload/confirm 或 assignment.publish。这是唯一发布门闩。
做题作业（problem_set）按 8 项补全要求后再发布。非做题（scenario / science_history / practical）收集 brief 与可选 discussion_goals，不要按 8 项拦发布。
「需要讨论」只是陪练提示，不是完成门闩；学生仍须用界面按钮交照片或书面产物（做题「提交作业」／情景与科学史「提交书面/照片」／实践「提交实践照片」）。

出题质量约束（老师 AI 出题时必须遵守）：
- 所有生成的题目必须自包含，不依赖配图。禁止使用"如图""见图""下图"等图引用词。
- 需要描述场景时，用文字完整说明对象、连接关系、方向、初始条件。
