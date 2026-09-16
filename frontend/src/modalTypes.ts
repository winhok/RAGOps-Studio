import type { DocumentRecord } from './types';

export type ModalState =
  | { kind: 'edit'; document: DocumentRecord | null }
  | { kind: 'history'; documents: DocumentRecord[] }
  | { kind: 'source'; document: DocumentRecord }
  | null;
