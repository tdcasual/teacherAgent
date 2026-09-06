import type { Skill } from '../../appTypes';

export const fallbackSkills: Skill[] = [
  {
    id: 'teacher-assignment-ops',
    title: '作业运营',
    desc: '作业进度、未交/逾期名单与发布归档。',
    instructions: '',
    prompts: ['列出今天未交作业的学生。'],
    examples: ['谁没交', '查看作业进度', '逾期名单'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'homework-generator',
    title: '作业生成',
    desc: '基于课堂讨论生成课后诊断与作业。',
    instructions: '',
    prompts: ['生成作业 A2403_2026-02-04，知识点 KP-M01,KP-E04，每个 5 题。'],
    examples: ['生成作业 A2403_2026-02-04', '渲染作业文档'],
    keywords: [],
    source_type: 'system',
  },
  {
    id: 'student-coach',
    title: '学生教练',
    desc: '学生侧讨论、作业批改与画像更新。',
    instructions: '',
    prompts: ['开始今天作业。'],
    examples: ['开始今天作业', '查看我的作业结果'],
    keywords: [],
    source_type: 'system',
  },
];

export const TEACHER_GREETING =
  '老师端已就绪。你可以直接提需求，例如：\n- 谁没交作业\n- 导入学生名册\n- 生成作业\n\n召唤规则：`$能力ID` 选择教学能力（未指定时自动推荐）。';

type RawSkill = {
  id: string;
  title?: string;
  desc?: string;
  instructions?: string;
  prompts?: string[];
  examples?: string[];
  source_type?: string;
  routing?: { keywords?: string[] };
};

export const buildSkill = (skill: RawSkill): Skill => {
  const prompts = Array.isArray(skill.prompts) ? skill.prompts.filter(Boolean) : [];
  const examples = Array.isArray(skill.examples) ? skill.examples.filter(Boolean) : [];
  const keywords = Array.isArray(skill.routing?.keywords)
    ? skill.routing.keywords.filter(Boolean)
    : [];
  const sourceType = (skill.source_type || 'system') as Skill['source_type'];
  return {
    id: skill.id,
    title: (skill.title || '').trim() || '未命名能力',
    desc: (skill.desc || '').trim(),
    instructions: (skill.instructions || '').trim(),
    prompts: prompts.length ? prompts : ['请描述你的需求。'],
    examples,
    keywords,
    source_type: sourceType,
  };
};
