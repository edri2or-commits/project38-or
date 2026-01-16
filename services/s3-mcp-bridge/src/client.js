/**
 * S3 MCP Bridge - Client
 *
 * Runs inside Claude Code sandbox.
 * Translates Stdio MCP messages to S3 objects.
 *
 * Architecture:
 *   Claude Code <--stdio--> This Bridge <--S3--> Server Adapter <--stdio--> Real MCP Server
 */

import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import { randomUUID } from "crypto";

export class S3McpBridgeClient {
  constructor(config) {
    this.bucket = config.bucket;
    this.prefix = config.prefix || "mcp-relay";
    this.sessionId = config.sessionId || `session-${Date.now()}-${randomUUID().slice(0, 8)}`;
    this.pollIntervalMs = config.pollIntervalMs || 250;
    this.timeoutMs = config.timeoutMs || 30000;

    this.s3 = new S3Client({
      region: config.region || "us-east-1",
      credentials: config.credentials ? {
        accessKeyId: config.credentials.accessKeyId,
        secretAccessKey: config.credentials.secretAccessKey
      } : undefined
    });

    this.pendingRequests = new Map();
    this.messageBuffer = "";
  }

  /**
   * Process incoming data from stdin
   */
  async processInput(chunk) {
    this.messageBuffer += chunk.toString();

    // Split on newlines (JSON-RPC messages are newline-delimited)
    const lines = this.messageBuffer.split("\n");
    this.messageBuffer = lines.pop() || ""; // Keep incomplete line

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        try {
          const message = JSON.parse(trimmed);
          await this.handleMessage(message);
        } catch (e) {
          console.error(`[S3Bridge] Failed to parse message: ${e.message}`);
        }
      }
    }
  }

  /**
   * Handle a single MCP message
   */
  async handleMessage(message) {
    const requestId = message.id !== undefined ? String(message.id) : `notify-${Date.now()}-${randomUUID().slice(0, 8)}`;
    const s3Key = `${this.prefix}/requests/${this.sessionId}/${requestId}.json`;

    // Upload request to S3
    await this.s3.send(new PutObjectCommand({
      Bucket: this.bucket,
      Key: s3Key,
      Body: JSON.stringify({
        ...message,
        _bridge: {
          sessionId: this.sessionId,
          requestId: requestId,
          timestamp: new Date().toISOString()
        }
      }),
      ContentType: "application/json"
    }));

    // If it's a notification (no id), we don't wait for response
    if (message.id === undefined) {
      return;
    }

    // Poll for response
    const responseKey = `${this.prefix}/responses/${this.sessionId}/${requestId}.json`;
    const response = await this.pollForResponse(responseKey, requestId);

    if (response) {
      // Write response to stdout
      process.stdout.write(JSON.stringify(response) + "\n");
    }
  }

  /**
   * Poll S3 for a response
   */
  async pollForResponse(key, requestId) {
    const startTime = Date.now();

    while (Date.now() - startTime < this.timeoutMs) {
      try {
        const result = await this.s3.send(new GetObjectCommand({
          Bucket: this.bucket,
          Key: key
        }));

        const bodyText = await result.Body.transformToString();
        const response = JSON.parse(bodyText);

        // Clean up response object
        try {
          await this.s3.send(new DeleteObjectCommand({
            Bucket: this.bucket,
            Key: key
          }));
        } catch (deleteErr) {
          // Non-critical, log and continue
          console.error(`[S3Bridge] Failed to delete response: ${deleteErr.message}`);
        }

        // Remove bridge metadata before returning
        delete response._bridge;
        return response;

      } catch (e) {
        if (e.name === "NoSuchKey") {
          // Response not ready yet, wait and retry
          await this.sleep(this.pollIntervalMs);
        } else {
          console.error(`[S3Bridge] Error polling for response: ${e.message}`);
          throw e;
        }
      }
    }

    // Timeout - return error response
    console.error(`[S3Bridge] Timeout waiting for response to request ${requestId}`);
    return {
      jsonrpc: "2.0",
      id: requestId,
      error: {
        code: -32000,
        message: "S3 Bridge timeout waiting for response"
      }
    };
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Start the bridge (listen on stdin)
   */
  start() {
    console.error(`[S3Bridge] Starting client bridge`);
    console.error(`[S3Bridge] Bucket: ${this.bucket}`);
    console.error(`[S3Bridge] Session: ${this.sessionId}`);

    process.stdin.on("data", (chunk) => this.processInput(chunk));

    process.stdin.on("end", () => {
      console.error("[S3Bridge] Stdin closed, exiting");
      process.exit(0);
    });
  }
}
