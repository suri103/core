// ============================================
// CoreDent PMS - MSW Server Setup
// Mock Service Worker server configuration
// ============================================

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Create the MSW server with our handlers
export const server = setupServer(...handlers);
