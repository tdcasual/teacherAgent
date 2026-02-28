import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeStringify from 'rehype-stringify';
import type { Schema } from 'hast-util-sanitize';
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

// KaTeX relies on inline styles for baseline/offset geometry (subscript/superscript layout).
// Allow only numeric positioning-related declarations instead of unbounded style attrs.
const KATEX_STYLE_RE =
  /^(?:\s*(?:height|width|min-width|left|top|margin-left|margin-right|padding-left|vertical-align|border-bottom-width)\s*:\s*-?\d*\.?\d+(?:em|ex|px|pt|pc|in|cm|mm|mu|%)?\s*;|\s*position\s*:\s*relative\s*;)+\s*$/;

type SanitizeAttributes = NonNullable<Schema['attributes']>;
type SanitizeAttribute = SanitizeAttributes[string][number];

const defaultAttributes = (defaultSchema.attributes ?? {}) as SanitizeAttributes;
const classNameAttribute: SanitizeAttribute = 'className';
const katexStyleAttribute: SanitizeAttribute = ['style', KATEX_STYLE_RE];

const katexSchema: Schema = {
  ...defaultSchema,
  attributes: {
    ...defaultAttributes,
    span: [...(defaultAttributes.span ?? []), classNameAttribute, katexStyleAttribute],
    div: [...(defaultAttributes.div ?? []), classNameAttribute, katexStyleAttribute],
    code: [...(defaultAttributes.code ?? []), classNameAttribute],
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

const escapeHtml = (text: string) =>
  String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

export const renderStreamingPlainText = (content: string) => {
  const normalized = String(content || '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n');
  return escapeHtml(normalized).replace(/\n/g, '<br/>');
};

const appendChartAccessToken = (path: string, accessToken: string) => {
  const token = String(accessToken || '').trim();
  if (!token) return path;
  const rawPath = String(path || '');
  const hashIndex = rawPath.indexOf('#');
  const baseAndQuery = hashIndex >= 0 ? rawPath.slice(0, hashIndex) : rawPath;
  const hashSuffix = hashIndex >= 0 ? rawPath.slice(hashIndex) : '';
  if (/(?:\?|&)access_token=/.test(baseAndQuery)) return rawPath;
  const separator = baseAndQuery.includes('?') ? '&' : '?';
  return `${baseAndQuery}${separator}access_token=${encodeURIComponent(token)}${hashSuffix}`;
};

export const absolutizeChartImageUrls = (html: string, apiBase: string, accessToken = '') => {
  const base = normalizeApiBase(apiBase);
  if (!base) return html;
  return html
    .replace(
      /(<img\b[^>]*\bsrc=["'])(\/charts\/[^"']+)(["'])/gi,
      (_, p1, p2, p3) => `${p1}${base}${appendChartAccessToken(String(p2), accessToken)}${p3}`,
    )
    .replace(
      /(<a\b[^>]*\bhref=["'])(\/charts\/[^"']+)(["'])/gi,
      (_, p1, p2, p3) => `${p1}${base}${appendChartAccessToken(String(p2), accessToken)}${p3}`,
    );
};
