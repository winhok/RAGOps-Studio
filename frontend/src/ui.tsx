import type { ReactNode } from 'react';

export type Tab = 'ask' | 'documents' | 'trace' | 'evaluation';

export const evidenceTypes = [
  'review_rule',
  'material_requirement',
  'arrival_rule',
  'maintenance_policy',
  'finance_policy',
  'service_workflow',
  'promotion_policy',
  'general',
] as const;

export const sampleQuestions = [
  ['Multi-source', '订单 A2026 的咖啡机退款金额是 3500 元，需要人工审核吗？准备材料时还要注意什么？'],
  ['Clarification', '我的咖啡机想申请退款，需要人工审核吗？'],
  ['Policy threshold', '蓝鲸科技现在的退款金额超过多少元需要人工审核？'],
  ['Unavailable evidence', '蓝鲸科技的咖啡机是否提供终身免费上门保养？'],
  ['No retrieval', '把“请尽快处理退款”改写得更礼貌。'],
] as const;

export const icons: Record<Tab, string> = {
  ask: '◈',
  documents: '▤',
  trace: '⌁',
  evaluation: '◫',
};

export const labels: Record<Tab, string> = {
  ask: 'Ask workspace',
  documents: 'Knowledge library',
  trace: 'Execution traces',
  evaluation: 'Evaluations',
};

export function label(value: string) {
  return value.replaceAll('_', ' ');
}

export function score(value: number | null) {
  return value === null ? '—' : value.toFixed(4);
}

export function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function Pill({ children, type = 'neutral' }: { children: ReactNode; type?: string }) {
  return <span className={`pill ${type}`}>{children}</span>;
}

export function Feedback({ error, notice }: { error: string; notice: string }) {
  return (
    <>
      {error ? <div role="alert" className="banner error">{error}</div> : null}
      {notice ? <div role="status" className="banner success">{notice}</div> : null}
    </>
  );
}
