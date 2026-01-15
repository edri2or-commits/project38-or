/**
 * Railway MCP HTTP Bridge
 *
 * This service exposes the official @railway/mcp-server over HTTP,
 * enabling Claude Code web sessions to interact with Railway.
 *
 * Architecture:
 *   Claude Code → HTTP → This Bridge → stdio → @railway/mcp-server → Railway API
 */

import express from 'express';
import { spawn } from 'child_process';
import { v4 as uuidv4 } from 'uuid';

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;
const BRIDGE_TOKEN = process.env.MCP_BRIDGE_TOKEN;
const RAILWAY_API_TOKEN = process.env.RAILWAY_API_TOKEN;

// Store active MCP sessions
const sessions = new Map();

/**
 * Authentication middleware
 */
function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!BRIDGE_TOKEN) {
    console.warn('Warning: MCP_BRIDGE_TOKEN not set, authentication disabled');
    return next();
  }

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing authorization header' });
  }

  const token = authHeader.substring(7);
  if (token !== BRIDGE_TOKEN) {
    return res.status(403).json({ error: 'Invalid token' });
  }

  next();
}

/**
 * Create or get MCP session
 */
function getOrCreateSession(sessionId) {
  if (sessions.has(sessionId)) {
    return sessions.get(sessionId);
  }

  console.log(`Creating new MCP session: ${sessionId}`);

  const mcpProcess = spawn('npx', ['-y', '@railway/mcp-server'], {
    env: {
      ...process.env,
      RAILWAY_API_TOKEN: RAILWAY_API_TOKEN
    },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  const session = {
    id: sessionId,
    process: mcpProcess,
    pendingRequests: new Map(),
    buffer: ''
  };

  // Handle stdout (MCP responses)
  mcpProcess.stdout.on('data', (data) => {
    session.buffer += data.toString();

    // Try to parse complete JSON-RPC messages
    const lines = session.buffer.split('\n');
    session.buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.trim()) {
        try {
          const response = JSON.parse(line);
          const requestId = response.id;

          if (requestId && session.pendingRequests.has(requestId)) {
            const { resolve } = session.pendingRequests.get(requestId);
            session.pendingRequests.delete(requestId);
            resolve(response);
          }
        } catch (e) {
          console.error('Failed to parse MCP response:', line);
        }
      }
    }
  });

  // Handle stderr (logs)
  mcpProcess.stderr.on('data', (data) => {
    console.log(`MCP [${sessionId}]:`, data.toString());
  });

  // Handle process exit
  mcpProcess.on('exit', (code) => {
    console.log(`MCP session ${sessionId} exited with code ${code}`);
    sessions.delete(sessionId);
  });

  sessions.set(sessionId, session);
  return session;
}

/**
 * Send request to MCP server and wait for response
 */
async function sendMcpRequest(session, method, params = {}) {
  const requestId = uuidv4();

  const request = {
    jsonrpc: '2.0',
    id: requestId,
    method,
    params
  };

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      session.pendingRequests.delete(requestId);
      reject(new Error('MCP request timeout'));
    }, 30000);

    session.pendingRequests.set(requestId, {
      resolve: (response) => {
        clearTimeout(timeout);
        resolve(response);
      },
      reject
    });

    session.process.stdin.write(JSON.stringify(request) + '\n');
  });
}

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'railway-mcp-bridge',
    sessions: sessions.size,
    railway_token_set: !!RAILWAY_API_TOKEN
  });
});

// Initialize MCP session
app.post('/mcp/initialize', authenticate, async (req, res) => {
  try {
    const sessionId = req.body.sessionId || uuidv4();
    const session = getOrCreateSession(sessionId);

    const response = await sendMcpRequest(session, 'initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: {
        name: 'railway-mcp-bridge',
        version: '1.0.0'
      }
    });

    res.json({
      sessionId,
      ...response
    });
  } catch (error) {
    console.error('Initialize error:', error);
    res.status(500).json({ error: error.message });
  }
});

// List available tools
app.get('/mcp/tools', authenticate, async (req, res) => {
  try {
    const sessionId = req.query.sessionId || 'default';
    const session = getOrCreateSession(sessionId);

    const response = await sendMcpRequest(session, 'tools/list', {});
    res.json(response);
  } catch (error) {
    console.error('Tools list error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Call a tool
app.post('/mcp/tools/call', authenticate, async (req, res) => {
  try {
    const { sessionId = 'default', name, arguments: args } = req.body;
    const session = getOrCreateSession(sessionId);

    const response = await sendMcpRequest(session, 'tools/call', {
      name,
      arguments: args
    });

    res.json(response);
  } catch (error) {
    console.error('Tool call error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Convenience endpoints for common Railway operations

// List projects
app.get('/railway/projects', authenticate, async (req, res) => {
  try {
    const session = getOrCreateSession('default');
    const response = await sendMcpRequest(session, 'tools/call', {
      name: 'list-projects',
      arguments: {}
    });
    res.json(response);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Deploy service
app.post('/railway/deploy', authenticate, async (req, res) => {
  try {
    const { projectId, serviceId, repo } = req.body;
    const session = getOrCreateSession('default');

    const response = await sendMcpRequest(session, 'tools/call', {
      name: 'deploy',
      arguments: { projectId, serviceId, repo }
    });
    res.json(response);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get deployment logs
app.get('/railway/logs/:deploymentId', authenticate, async (req, res) => {
  try {
    const { deploymentId } = req.params;
    const session = getOrCreateSession('default');

    const response = await sendMcpRequest(session, 'tools/call', {
      name: 'get-deployment-logs',
      arguments: { deploymentId }
    });
    res.json(response);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// MCP SSE endpoint for streaming (future)
app.get('/mcp/sse', authenticate, (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  res.write('data: {"status":"connected"}\n\n');

  // Keep connection alive
  const keepAlive = setInterval(() => {
    res.write(': keepalive\n\n');
  }, 15000);

  req.on('close', () => {
    clearInterval(keepAlive);
  });
});

// Cleanup on shutdown
process.on('SIGTERM', () => {
  console.log('Shutting down MCP bridge...');
  for (const [sessionId, session] of sessions) {
    console.log(`Closing session ${sessionId}`);
    session.process.kill();
  }
  process.exit(0);
});

app.listen(PORT, () => {
  console.log(`Railway MCP Bridge running on port ${PORT}`);
  console.log(`Railway API Token: ${RAILWAY_API_TOKEN ? 'SET' : 'NOT SET'}`);
  console.log(`Bridge Token: ${BRIDGE_TOKEN ? 'SET' : 'NOT SET'}`);
});
