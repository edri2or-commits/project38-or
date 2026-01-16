/**
 * GCS MCP Relay Server
 *
 * This service polls a GCS bucket for MCP requests from Claude Code
 * and forwards them to the MCP Gateway running on the same Railway project.
 *
 * Architecture:
 *   Claude Code → GCS (whitelisted) → This Relay → MCP Gateway → Services
 *                                          ↓
 *                                   Response back to GCS
 *
 * Environment Variables:
 *   GCS_BUCKET: Bucket name (default: project38-mcp-relay)
 *   GCS_PREFIX: Object prefix (default: mcp-relay)
 *   MCP_GATEWAY_URL: MCP Gateway URL (default: http://localhost:8080/mcp)
 *   GOOGLE_APPLICATION_CREDENTIALS_JSON: SA key JSON (required)
 *   POLL_INTERVAL_MS: Polling interval (default: 1000)
 */

import { Storage } from '@google-cloud/storage';
import express from 'express';

// Configuration
const config = {
  bucket: process.env.GCS_BUCKET || 'project38-mcp-relay',
  prefix: process.env.GCS_PREFIX || 'mcp-relay',
  mcpUrl: process.env.MCP_GATEWAY_URL || 'http://localhost:8080/mcp',
  pollInterval: parseInt(process.env.POLL_INTERVAL_MS || '1000', 10),
  port: parseInt(process.env.PORT || '3002', 10)
};

// Initialize GCS client
let storage;
if (process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON) {
  const credentials = JSON.parse(process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON);
  storage = new Storage({ credentials });
  console.log('Using credentials from GOOGLE_APPLICATION_CREDENTIALS_JSON');
} else if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
  storage = new Storage();
  console.log('Using credentials from GOOGLE_APPLICATION_CREDENTIALS file');
} else {
  console.error('ERROR: No GCS credentials found!');
  console.error('Set GOOGLE_APPLICATION_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS');
  process.exit(1);
}

const bucket = storage.bucket(config.bucket);

// Express app for health checks
const app = express();
app.use(express.json());

// Stats
const stats = {
  requestsProcessed: 0,
  errors: 0,
  lastPoll: null,
  lastRequest: null,
  startTime: new Date()
};

/**
 * Poll for new requests in GCS
 */
async function pollForRequests() {
  try {
    const requestsPrefix = `${config.prefix}/requests/`;
    const [files] = await bucket.getFiles({ prefix: requestsPrefix });

    stats.lastPoll = new Date();

    for (const file of files) {
      // Skip if not a JSON file
      if (!file.name.endsWith('.json')) continue;

      try {
        await processRequest(file);
      } catch (error) {
        console.error(`Error processing ${file.name}:`, error.message);
        stats.errors++;
      }
    }
  } catch (error) {
    console.error('Poll error:', error.message);
    stats.errors++;
  }
}

/**
 * Process a single request from GCS
 */
async function processRequest(file) {
  console.log(`Processing: ${file.name}`);

  // Download request
  const [content] = await file.download();
  const request = JSON.parse(content.toString());

  // Extract metadata
  const sessionId = request._bridge?.sessionId || 'unknown';
  const requestId = request._bridge?.requestId || request.id;
  const responsePath = request._bridge?.responsePath;

  if (!responsePath) {
    console.error(`No response path in ${file.name}`);
    await file.delete();
    return;
  }

  // Forward to MCP Gateway
  let response;
  try {
    const mcpRequest = { ...request };
    delete mcpRequest._bridge; // Remove metadata before forwarding

    const mcpResponse = await fetch(config.mcpUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(mcpRequest)
    });

    response = await mcpResponse.json();
  } catch (error) {
    response = {
      jsonrpc: '2.0',
      id: request.id,
      error: {
        code: -32000,
        message: `MCP Gateway error: ${error.message}`
      }
    };
  }

  // Upload response to GCS
  const responseFile = bucket.file(responsePath);
  await responseFile.save(JSON.stringify(response), {
    contentType: 'application/json'
  });

  // Delete request (processed)
  await file.delete();

  stats.requestsProcessed++;
  stats.lastRequest = new Date();

  console.log(`Completed: ${requestId} -> ${responsePath}`);
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'gcs-mcp-relay',
    config: {
      bucket: config.bucket,
      prefix: config.prefix,
      mcpUrl: config.mcpUrl,
      pollInterval: config.pollInterval
    },
    stats: {
      requestsProcessed: stats.requestsProcessed,
      errors: stats.errors,
      lastPoll: stats.lastPoll,
      lastRequest: stats.lastRequest,
      uptime: Math.floor((Date.now() - stats.startTime.getTime()) / 1000)
    }
  });
});

// Manual trigger for testing
app.post('/poll', async (req, res) => {
  try {
    await pollForRequests();
    res.json({ success: true, stats });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start server
app.listen(config.port, () => {
  console.log('='.repeat(60));
  console.log('GCS MCP Relay Server Started');
  console.log('='.repeat(60));
  console.log(`Health endpoint: http://localhost:${config.port}/health`);
  console.log(`Bucket: gs://${config.bucket}/${config.prefix}/`);
  console.log(`MCP Gateway: ${config.mcpUrl}`);
  console.log(`Poll Interval: ${config.pollInterval}ms`);
  console.log('='.repeat(60));
});

// Start polling loop
console.log('Starting GCS polling loop...');
setInterval(pollForRequests, config.pollInterval);

// Initial poll
pollForRequests();
