/**
 * S3 MCP Bridge - Server
 *
 * Runs on your infrastructure (Railway, etc).
 * Polls S3 for requests, forwards to real MCP server, uploads responses.
 *
 * Architecture:
 *   Claude Code <--S3--> This Server <--stdio/http--> Real MCP Server
 */

import { S3Client, ListObjectsV2Command, GetObjectCommand, PutObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import { spawn } from "child_process";
import { randomUUID } from "crypto";

export class S3McpBridgeServer {
  constructor(config) {
    this.bucket = config.bucket;
    this.prefix = config.prefix || "mcp-relay";
    this.pollIntervalMs = config.pollIntervalMs || 500;

    // MCP server configuration
    this.mcpCommand = config.mcpCommand; // e.g., "node"
    this.mcpArgs = config.mcpArgs || []; // e.g., ["./mcp-server.js"]
    this.mcpUrl = config.mcpUrl; // Alternative: HTTP-based MCP server URL

    this.s3 = new S3Client({
      region: config.region || "us-east-1",
      credentials: config.credentials ? {
        accessKeyId: config.credentials.accessKeyId,
        secretAccessKey: config.credentials.secretAccessKey
      } : undefined
    });

    this.running = false;
    this.processedRequests = new Set(); // Track processed requests to avoid duplicates
    this.mcpProcess = null;
    this.pendingResponses = new Map();
  }

  /**
   * Start the MCP subprocess (for stdio-based MCP servers)
   */
  startMcpProcess() {
    if (!this.mcpCommand) {
      throw new Error("mcpCommand is required for stdio mode");
    }

    console.log(`[S3Bridge Server] Starting MCP process: ${this.mcpCommand} ${this.mcpArgs.join(" ")}`);

    this.mcpProcess = spawn(this.mcpCommand, this.mcpArgs, {
      stdio: ["pipe", "pipe", "inherit"]
    });

    this.mcpProcess.stdout.on("data", (data) => {
      this.handleMcpResponse(data.toString());
    });

    this.mcpProcess.on("exit", (code) => {
      console.log(`[S3Bridge Server] MCP process exited with code ${code}`);
      this.running = false;
    });

    this.mcpProcess.on("error", (err) => {
      console.error(`[S3Bridge Server] MCP process error: ${err.message}`);
    });
  }

  /**
   * Handle response from MCP process
   */
  handleMcpResponse(data) {
    const lines = data.split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        try {
          const response = JSON.parse(trimmed);
          const requestId = response.id !== undefined ? String(response.id) : null;

          if (requestId && this.pendingResponses.has(requestId)) {
            const { sessionId, resolve } = this.pendingResponses.get(requestId);
            this.pendingResponses.delete(requestId);
            resolve({ response, sessionId, requestId });
          }
        } catch (e) {
          console.error(`[S3Bridge Server] Failed to parse MCP response: ${e.message}`);
        }
      }
    }
  }

  /**
   * Send request to MCP process and wait for response
   */
  async sendToMcpProcess(request, sessionId) {
    return new Promise((resolve, reject) => {
      const requestId = request.id !== undefined ? String(request.id) : null;

      if (requestId) {
        this.pendingResponses.set(requestId, { sessionId, resolve });
      }

      // Remove bridge metadata before sending to real MCP
      const cleanRequest = { ...request };
      delete cleanRequest._bridge;

      this.mcpProcess.stdin.write(JSON.stringify(cleanRequest) + "\n");

      // If it's a notification, resolve immediately
      if (!requestId) {
        resolve(null);
      }

      // Timeout after 30 seconds
      setTimeout(() => {
        if (requestId && this.pendingResponses.has(requestId)) {
          this.pendingResponses.delete(requestId);
          reject(new Error("MCP request timeout"));
        }
      }, 30000);
    });
  }

  /**
   * Send request to HTTP-based MCP server
   */
  async sendToMcpHttp(request, sessionId) {
    const cleanRequest = { ...request };
    delete cleanRequest._bridge;

    const response = await fetch(this.mcpUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(cleanRequest)
    });

    if (!response.ok) {
      throw new Error(`MCP HTTP error: ${response.status}`);
    }

    const result = await response.json();
    return {
      response: result,
      sessionId,
      requestId: request.id !== undefined ? String(request.id) : null
    };
  }

  /**
   * Process a single request from S3
   */
  async processRequest(key) {
    try {
      // Download request
      const result = await this.s3.send(new GetObjectCommand({
        Bucket: this.bucket,
        Key: key
      }));

      const bodyText = await result.Body.transformToString();
      const request = JSON.parse(bodyText);

      const bridgeData = request._bridge || {};
      const sessionId = bridgeData.sessionId || "unknown";
      const requestId = bridgeData.requestId || (request.id !== undefined ? String(request.id) : null);

      console.log(`[S3Bridge Server] Processing request ${requestId} from session ${sessionId}`);

      // Forward to MCP server
      let responseData;
      if (this.mcpUrl) {
        responseData = await this.sendToMcpHttp(request, sessionId);
      } else if (this.mcpProcess) {
        responseData = await this.sendToMcpProcess(request, sessionId);
      } else {
        throw new Error("No MCP server configured");
      }

      // Upload response if we got one
      if (responseData && responseData.response) {
        const responseKey = `${this.prefix}/responses/${sessionId}/${requestId}.json`;

        await this.s3.send(new PutObjectCommand({
          Bucket: this.bucket,
          Key: responseKey,
          Body: JSON.stringify(responseData.response),
          ContentType: "application/json"
        }));

        console.log(`[S3Bridge Server] Uploaded response for ${requestId}`);
      }

      // Delete the request (mark as processed)
      await this.s3.send(new DeleteObjectCommand({
        Bucket: this.bucket,
        Key: key
      }));

    } catch (e) {
      console.error(`[S3Bridge Server] Error processing request ${key}: ${e.message}`);
    }
  }

  /**
   * Poll S3 for new requests
   */
  async pollForRequests() {
    try {
      const listResult = await this.s3.send(new ListObjectsV2Command({
        Bucket: this.bucket,
        Prefix: `${this.prefix}/requests/`
      }));

      const objects = listResult.Contents || [];

      for (const obj of objects) {
        const key = obj.Key;

        // Skip if already processed (in-flight)
        if (this.processedRequests.has(key)) {
          continue;
        }

        // Mark as being processed
        this.processedRequests.add(key);

        // Process asynchronously
        this.processRequest(key).finally(() => {
          // Remove from processed set after completion
          this.processedRequests.delete(key);
        });
      }
    } catch (e) {
      console.error(`[S3Bridge Server] Error polling S3: ${e.message}`);
    }
  }

  /**
   * Start the server
   */
  async start() {
    console.log(`[S3Bridge Server] Starting server`);
    console.log(`[S3Bridge Server] Bucket: ${this.bucket}`);
    console.log(`[S3Bridge Server] Prefix: ${this.prefix}`);

    this.running = true;

    // Start MCP subprocess if configured
    if (this.mcpCommand) {
      this.startMcpProcess();
    }

    // Main polling loop
    while (this.running) {
      await this.pollForRequests();
      await this.sleep(this.pollIntervalMs);
    }
  }

  /**
   * Stop the server
   */
  stop() {
    console.log("[S3Bridge Server] Stopping server");
    this.running = false;

    if (this.mcpProcess) {
      this.mcpProcess.kill();
    }
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
