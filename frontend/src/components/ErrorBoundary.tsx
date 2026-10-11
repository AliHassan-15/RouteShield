import { Component } from 'react';
import type { ReactNode } from 'react';
import { Button } from './controls';
import { Brand, Icon } from './icons';
import { TickDivider } from './surfaces';

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return <div className="fallback-screen"><header><Brand /></header><main><p className="micro">Interface unavailable</p><TickDivider /><Icon name="warning" width="32" height="32" /><h1>Restore your workspace</h1><p>An unexpected interface error interrupted this view. Reload to start a fresh session.</p><Button variant="primary" onClick={() => window.location.reload()}><Icon name="refresh" />Reload workspace</Button></main></div>;
  }
}
