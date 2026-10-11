import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { createQueryClient } from './api/query';
import { ErrorBoundary } from './components/ErrorBoundary';
import './style.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing application root.');

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary><QueryClientProvider client={createQueryClient()}>
      <App />
    </QueryClientProvider></ErrorBoundary>
  </StrictMode>,
);
