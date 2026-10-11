import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { BottomSheet } from './BottomSheet';
import { Button, IconButton, Input, SegmentedControl, Select, Slider, Tabs } from './controls';
import { ErrorBoundary } from './ErrorBoundary';
import { EmptyState, ErrorState, Popover, RiskBadge, RiskBar, Skeleton, Toast, Tooltip, floatingPosition, riskPresentation } from './surfaces';
import { keyboardSnap, nearestSnap, snapOffset } from '../lib/sheet';
import type { RiskLevel } from '../api/types';

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });
test('buttons preserve native activation, disabled and loading semantics', () => {
  const action = vi.fn();
  render(<><Button onClick={action}>Act</Button><Button disabled onClick={action}>Disabled</Button><Button loading onClick={action}>Working</Button><IconButton icon="close" label="Close panel" onClick={action} /></>);
  fireEvent.click(screen.getByRole('button', { name: 'Act' }));
  fireEvent.click(screen.getByRole('button', { name: 'Disabled' }));
  fireEvent.click(screen.getByRole('button', { name: /Working.*working/ }));
  expect(action).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: /Working.*working/ }).getAttribute('aria-busy')).toBe('true');
  expect(screen.getByRole('button', { name: 'Close panel' }).tagName).toBe('BUTTON');
});
test('input has linked label and error without losing exact input text', () => {
  function Example() { const [value, update] = useState('30000.01'); return <Input label="Load" suffix="lb" error="Check load" value={value} onChange={e => update(e.target.value)} />; }
  render(<Example />);
  const input = screen.getByLabelText('Load');
  fireEvent.change(input, { target: { value: '40000.01' } });
  expect((input as HTMLInputElement).value).toBe('40000.01');
  expect(input.getAttribute('aria-invalid')).toBe('true');
  expect(document.getElementById(input.getAttribute('aria-describedby') ?? '')?.textContent).toContain('Check load');
});
test('select uses a labeled native keyboard-capable control', () => {
  const change = vi.fn(); render(<Select label="Spacing" onChange={change}><option>10 mi</option><option>25 mi</option></Select>);
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '25 mi' } });
  expect(change).toHaveBeenCalledOnce(); expect(screen.getByLabelText('Spacing').tagName).toBe('SELECT');
});
test('slider exposes value, units and native range semantics', () => {
  const change = vi.fn(); render(<Slider label="Hour" value={12} onChange={change} unit="h" />);
  const slider = screen.getByRole('slider'); fireEvent.change(slider, { target: { value: '13' } });
  expect(change).toHaveBeenCalledWith(13); expect(slider.getAttribute('aria-valuetext')).toBe('12 h'); expect(slider.getAttribute('max')).toBe('48');
});
test('segmented control moves focus, selection, Home and End', () => {
  function Example() { const [value, set] = useState('a'); return <SegmentedControl label="Choice" value={value} onChange={set} options={[{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }, { value: 'c', label: 'C' }]} />; }
  render(<Example />); const a = screen.getByRole('radio', { name: 'A' }); a.focus(); fireEvent.keyDown(a, { key: 'ArrowRight' });
  const b = screen.getByRole('radio', { name: 'B' }); expect(document.activeElement).toBe(b); expect(b.getAttribute('aria-checked')).toBe('true');
  fireEvent.keyDown(b, { key: 'End' }); expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'C' }));
  fireEvent.keyDown(document.activeElement!, { key: 'Home' }); expect(document.activeElement).toBe(a);
});
test('tabs implement automatic activation, wrapping and linked panels', () => {
  render(<Tabs label="Results" tabs={[{ id: 'one', label: 'One', content: 'First panel' }, { id: 'two', label: 'Two', content: 'Second panel' }]} />);
  const one = screen.getByRole('tab', { name: 'One' }); one.focus(); fireEvent.keyDown(one, { key: 'ArrowLeft' });
  expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Two' })); expect(screen.getByRole('tabpanel').textContent).toBe('Second panel');
  fireEvent.keyDown(document.activeElement!, { key: 'Home' }); expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(one.id);
});
test('popover fallback focuses content and Escape restores trigger focus', () => {
  render(<Popover label="Details"><p>Content</p></Popover>); const trigger = screen.getByRole('button', { name: 'Details' }); fireEvent.click(trigger);
  expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true);
  fireEvent.keyDown(document.activeElement!, { key: 'Escape' }); expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(trigger);
});
test('popover positions inside the viewport and prefers above when necessary', () => {
  expect(floatingPosition(new DOMRect(390, 500, 40, 44), 300, 180, { width: 420, height: 600 })).toEqual({ left: 112, top: 312 });
});
test('tooltip appears on focus and dismisses on Escape', () => {
  render(<Tooltip label="Explanation"><IconButton label="Help" icon="info" /></Tooltip>);
  fireEvent.focus(screen.getByRole('button')); expect(screen.getByRole('tooltip').textContent).toBe('Explanation'); fireEvent.keyDown(screen.getByRole('button'), { key: 'Escape' }); expect(screen.queryByRole('tooltip')).toBeNull();
});
test('toast is announced and its keyboard dismissal completes after exit', async () => {
  vi.useFakeTimers(); const dismiss = vi.fn(); render(<Toast onDismiss={dismiss}>Saved</Toast>);
  expect(screen.getByRole('status').textContent).toContain('Saved'); fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' })); await act(() => vi.advanceTimersByTimeAsync(201)); expect(dismiss).toHaveBeenCalledOnce();
});
test.each(Object.keys(riskPresentation) as RiskLevel[])('risk badge %s includes unique shape and a text label', level => {
  const { container } = render(<RiskBadge level={level} />); expect(screen.getByText(riskPresentation[level].label)).toBeTruthy(); expect(container.querySelector('[data-shape]')?.getAttribute('data-shape')).toBe(riskPresentation[level].shape); expect(container.querySelector('svg path')).toBeTruthy();
});
test('risk strip uses supplied miles, labels UNKNOWN and never classifies', () => {
  const { container } = render(<RiskBar segments={[{ level: 'LOW', miles: 3 }, { level: 'UNKNOWN', miles: 1 }]} />);
  expect(screen.getByRole('img').getAttribute('aria-label')).toContain('Unknown 1 miles'); expect((container.querySelector('.risk-low') as HTMLElement).style.flexGrow).toBe('0.75');
});
test.each([0, 300, 492])('sheet nearest snap has a stable position for offset %s', offset => {
  expect(nearestSnap(offset, 600)).toBe(offset === 0 ? 'full' : offset === 300 ? 'half' : 'peek');
  expect(snapOffset(nearestSnap(offset, 600), 600)).toBe(offset);
});
test('sheet snap keys clamp and exact ties select the more open snap', () => {
  expect(keyboardSnap('full', 'ArrowUp')).toBe('full'); expect(keyboardSnap('peek', 'ArrowDown')).toBe('peek'); expect(keyboardSnap('half', 'Escape')).toBe('peek'); expect(nearestSnap(150, 600)).toBe('full');
});
test('sheet keyboard handle announces snaps and Escape retains handle focus', () => {
  const { container } = render(<BottomSheet><button>Inside</button></BottomSheet>);
  const handle = screen.getByRole('button', { name: /Route console: peek/ }); handle.focus(); fireEvent.keyDown(handle, { key: 'ArrowUp' }); expect(container.querySelector('[data-snap]')?.getAttribute('data-snap')).toBe('half');
  fireEvent.keyDown(handle, { key: 'Home' }); expect(container.querySelector('[data-snap]')?.getAttribute('data-snap')).toBe('full'); const inside = screen.getByRole('button', { name: 'Inside' }); inside.focus(); fireEvent.keyDown(inside, { key: 'Escape' }); expect(document.activeElement).toBe(handle); expect(handle.getAttribute('aria-expanded')).toBe('false');
});
test('sheet pointer drag snaps while cancelled drags leave state unchanged', () => {
  const { container } = render(<BottomSheet><p>Content</p></BottomSheet>);
  const handle = screen.getByRole('button', { name: /Route console: peek/ });
  // JSDOM has no native PointerEvent; a MouseEvent with pointerId exercises the handlers.
  const pointer = (type: string, y: number) => { const e = new MouseEvent(type, { bubbles: true, button: 0, clientY: y }); Object.defineProperty(e, 'pointerId', { value: 1 }); fireEvent(handle, e); };
  pointer('pointerdown', 600); pointer('pointermove', 400); pointer('pointerup', 400); expect(container.querySelector('[data-snap]')?.getAttribute('data-snap')).toBe('half');
  pointer('pointerdown', 400); pointer('pointermove', 50); pointer('pointercancel', 50); expect(container.querySelector('[data-snap]')?.getAttribute('data-snap')).toBe('half');
});
test('empty, error and loading states have useful text and recovery', () => {
  const recover = vi.fn(); render(<><EmptyState title="No trips">Choose a trip.</EmptyState><ErrorState title="Unavailable" action="Retry" onRecover={recover} requestId="test-id">Try again.</ErrorState><Skeleton label="Loading data" /></>);
  expect((screen.getByLabelText('Request ID') as HTMLInputElement).value).toBe('test-id'); fireEvent.click(screen.getByRole('button', { name: 'Retry' })); expect(recover).toHaveBeenCalledOnce(); expect(screen.getByRole('status', { name: 'Loading data' }).getAttribute('aria-label')).toBe('Loading data');
});
test('global boundary uses branded recovery without leaking the thrown diagnostic', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  function Crash(): never { throw new Error('PRIVATE_DIAGNOSTIC_DO_NOT_RENDER'); }
  render(<ErrorBoundary><Crash /></ErrorBoundary>); expect(screen.getByRole('button', { name: 'Reload workspace' })).toBeTruthy(); expect(document.body.textContent).not.toContain('PRIVATE_DIAGNOSTIC');
});
