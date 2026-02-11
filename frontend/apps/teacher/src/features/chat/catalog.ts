import type { Skill } from '../../appTypes'

export const fallbackSkills: Skill[] = [
  {
    id: 'physics-teacher-ops',
    title: '教师运营',
    desc: '考试分析、课前检测、教学备课与课堂讨论。',
    instructions: '',
    prompts: ['列出所有考试，并给出最新考试概览。'],
    examples: ['列出考试', '生成课前检测清单', '做一次考试分析'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-homework-generator',
    title: '作业生成',
    desc: '基于课堂讨论生成课后诊断与作业。',
    instructions: '',
    prompts: ['生成作业 A2403_2026-02-04，知识点 KP-M01,KP-E04，每个 5 题。'],
    examples: ['生成作业 A2403_2026-02-04', '渲染作业文档'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-lesson-capture',
    title: '课堂采集',
    desc: '课堂材料文字识别并抽取例题与讨论结构。',
    instructions: '',
    prompts: ['采集课堂材料 L2403_2026-02-04，主题"静电场综合"。'],
    examples: ['采集课堂材料 L2403_2026-02-04', '列出课程'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-student-coach',
    title: '学生教练',
    desc: '学生侧讨论、作业批改与画像更新。',
    instructions: '',
    prompts: ['查看学生画像 高二2403班_武熙语。'],
    examples: ['查看学生画像 武熙语', '开始今天作业'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-student-focus',
    title: '学生重点分析',
    desc: '针对某个学生进行重点诊断与画像更新。',
    instructions: '',
    prompts: ['请分析学生 高二2403班_武熙语 的最近作业表现。'],
    examples: ['分析学生 高二2403班_武熙语'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-core-examples',
    title: '核心例题库',
    desc: '登记核心例题、标准解法与变式题。',
    instructions: '',
    prompts: ['登记核心例题 CE001，知识点 KP-M01。'],
    examples: ['登记核心例题 CE001', '生成变式题 3 道'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'physics-llm-routing',
    title: '模型路由管理',
    desc: '按任务类型配置模型路由，支持仿真与回滚。',
    instructions: '',
    prompts: ['先读取当前路由配置，再给我一个三类任务分流方案。'],
    examples: ['查看当前模型路由', '仿真 physics-homework-generator 的 chat.agent', '回滚到路由版本 3'],
    keywords: [],
    source_type: 'system',
  },
]

export const TEACHER_GREETING =
  '老师端已就绪。你可以直接提需求，例如：\n- 列出考试\n- 导入学生名册\n- 生成作业\n\n召唤规则：`$skill` 选择技能（未指定时自动路由）。'

export const buildSkill = (skill: { id: string; title?: string; desc?: string; instructions?: string; prompts?: string[]; examples?: string[]; source_type?: string; routing?: any }): Skill => {
  const prompts = Array.isArray(skill.prompts) ? skill.prompts.filter(Boolean) : []
  const examples = Array.isArray(skill.examples) ? skill.examples.filter(Boolean) : []
  const keywords = Array.isArray(skill.routing?.keywords) ? skill.routing.keywords.filter(Boolean) : []
  const sourceType = (skill.source_type || 'system') as Skill['source_type']
  return {
    id: skill.id,
    title: (skill.title || '').trim() || '未命名技能',
    desc: (skill.desc || '').trim(),
    instructions: (skill.instructions || '').trim(),
    prompts: prompts.length ? prompts : ['请描述你的需求。'],
    examples,
    keywords,
    source_type: sourceType,
  }
}
