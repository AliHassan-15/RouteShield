import { useRef, useState } from 'react';
import { Button } from './controls';
export function RequestId({ id, onCopied }: { id: string; onCopied?: (message: string) => void }) {
  const input = useRef<HTMLInputElement>(null), [notice, setNotice] = useState('');
  const report = (text: string) => { setNotice(text); onCopied?.(text); };
  return <div><div className="request-chip"><input ref={input} aria-label="Request ID" className="mono" readOnly value={id} onFocus={e => e.currentTarget.select()} /><Button variant="ghost" onClick={async () => { try { await navigator.clipboard.writeText(id); report('Request ID copied.'); } catch { input.current?.focus(); input.current?.select(); report('Request ID selected. Use your copy shortcut.'); } }}>{notice === 'Request ID copied.' ? 'Copied' : 'Copy ID'}</Button></div><span className="sr-only" role="status">{notice}</span></div>;
}
