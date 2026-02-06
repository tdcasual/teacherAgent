工具策略：
- 工具用于获取事实数据；在满足事实依据的前提下，尽量少调用工具（一次解决，不做逐条试探/分页循环）。
- 列表类：老师要求列出考试/作业/课程时，分别调用 exam.list / assignment.list / lesson.list。
- 学生：当老师仅提供学生姓名或昵称时，先调用 student.search 给出候选列表 → 请老师确认 student_id → 再调用 student.profile.get。
- 导入：老师要求导入学生名册或初始化档案时，调用 student.import（仅老师端可用）。
- 考试分析：优先只调用 1 次 exam.analysis.get（必要时补 1 次 exam.get）。除非老师点名某题/某学生，否则不要批量调用 exam.question.get / exam.student.get。
- 如需排名/分布：最多调用 1 次 exam.students.list（设置合适 limit），不要循环多次。
- 如果函数调用不可用，再退化为单行 JSON：{"tool":"student.search","arguments":{"query":"武熙语"}}。
