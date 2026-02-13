import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeStringify from 'rehype-stringify';
import { visit } from 'unist-util-visit';
import type { Node } from 'unist';
import { normalizeApiBase } from './apiBase';

type MarkdownNode = {
  type?: string;
  value?: unknown;
  children?: MarkdownNode[];
};

const asMarkdownNode = (value: unknown): MarkdownNode | null => {
  if (!value || typeof value !== 'object') return null;
  return value as MarkdownNode;
};

const asMarkdownParent = (value: unknown): (MarkdownNode & { children: MarkdownNode[] }) | null => {
  const node = asMarkdownNode(value);
  if (!node || !Array.isArray(node.children)) return null;
  return node as MarkdownNode & { children: MarkdownNode[] };
};

const removeEmptyParagraphs = () => {
  return (tree: Node) => {
    visit(tree, 'paragraph', (node: unknown, index: number | null | undefined, parent: unknown) => {
      const parentNode = asMarkdownParent(parent);
      const paragraph = asMarkdownNode(node);
      if (!parentNode || !paragraph || typeof index !== 'number') return;
      if (!Array.isArray(paragraph.children) || paragraph.children.length === 0) {
        parentNode.children.splice(index, 1);
      }
    });
  };
};

const remarkLatexBrackets = () => {
  return (tree: Node) => {
    visit(tree, 'text', (node: unknown, index: number | null | undefined, parent: unknown) => {
      const parentNode = asMarkdownParent(parent);
      const textNode = asMarkdownNode(node);
      if (!parentNode || !textNode || typeof index !== 'number') return;
      if (parentNode.type === 'inlineMath' || parentNode.type === 'math') return;

      const value = String(textNode.value || '');
      if (!value.includes('\\[') && !value.includes('\\(')) return;

      const nodes: MarkdownNode[] = [];
      let pos = 0;

      const findUnescaped = (token: string, start: number) => {
        let idx = value.indexOf(token, start);
        while (idx > 0 && value[idx - 1] === '\\') {
          idx = value.indexOf(token, idx + 1);
        }
        return idx;
      };

      while (pos < value.length) {
        const nextDisplay = findUnescaped('\\[', pos);
        const nextInline = findUnescaped('\\(', pos);
        let next = -1;
        let mode: 'display' | 'inline' | '' = '';

        if (nextDisplay !== -1 && (nextInline === -1 || nextDisplay < nextInline)) {
          next = nextDisplay;
          mode = 'display';
        } else if (nextInline !== -1) {
          next = nextInline;
          mode = 'inline';
        }

        if (next === -1) {
          nodes.push({ type: 'text', value: value.slice(pos) });
          break;
        }

        if (next > pos) nodes.push({ type: 'text', value: value.slice(pos, next) });

        const closeToken = mode === 'display' ? '\\]' : '\\)';
        const end = findUnescaped(closeToken, next + 2);
        if (end === -1) {
          nodes.push({ type: 'text', value: value.slice(next) });
          break;
        }

        const mathValue = value.slice(next + 2, end);
        nodes.push({ type: mode === 'display' ? 'math' : 'inlineMath', value: mathValue });
        pos = end + 2;
      }

      if (nodes.length) {
        parentNode.children.splice(index, 1, ...nodes);
        return index + nodes.length;
      }
    });
  };
};

const katexSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span || []), 'className', 'style'],
    div: [...(defaultSchema.attributes?.div || []), 'className', 'style'],
    code: [...(defaultSchema.attributes?.code || []), 'className'],
  },
};

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(removeEmptyParagraphs)
  .use(remarkLatexBrackets)
  .use(remarkRehype)
  .use(rehypeKatex)
  .use(rehypeSanitize, katexSchema)
  .use(rehypeStringify);

const findUnescapedToken = (value: string, token: string, start: number) => {
  let idx = value.indexOf(token, start);
  while (idx > 0 && value[idx - 1] === '\\') {
    idx = value.indexOf(token, idx + 1);
  }
  return idx;
};

const normalizeMathDelimiters = (content: string) => {
  if (!content) return '';
  let pos = 0;
  let output = '';

  while (pos < content.length) {
    const nextDisplay = findUnescapedToken(content, '\\[', pos);
    const nextInline = findUnescapedToken(content, '\\(', pos);
    let next = -1;
    let mode: 'display' | 'inline' | '' = '';

    if (nextDisplay !== -1 && (nextInline === -1 || nextDisplay < nextInline)) {
      next = nextDisplay;
      mode = 'display';
    } else if (nextInline !== -1) {
      next = nextInline;
      mode = 'inline';
    }

    if (next === -1) {
      output += content.slice(pos);
      break;
    }

    output += content.slice(pos, next);
    const closeToken = mode === 'display' ? '\\]' : '\\)';
    const end = findUnescapedToken(content, closeToken, next + 2);
    if (end === -1) {
      output += content.slice(next);
      break;
    }

    const mathValue = content.slice(next + 2, end);
    output += mode === 'display' ? `\n$$\n${mathValue}\n$$\n` : `$${mathValue}$`;
    pos = end + 2;
  }

  return output;
};

export const renderMarkdown = (content: string) => {
  const normalized = normalizeMathDelimiters(content || '');
  const result = processor.processSync(normalized);
  return String(result);
};

export const absolutizeChartImageUrls = (html: string, apiBase: string) => {
  const base = normalizeApiBase(apiBase);
  if (!base) return html;
  return html
    .replace(
      /(<img\b[^>]*\bsrc=["'])(\/charts\/[^"']+)(["'])/gi,
      (_, p1, p2, p3) => `${p1}${base}${p2}${p3}`,
    )
    .replace(
      /(<a\b[^>]*\bhref=["'])(\/charts\/[^"']+)(["'])/gi,
      (_, p1, p2, p3) => `${p1}${base}${p2}${p3}`,
    );
};
