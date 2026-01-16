/**
 * GCS MCP Bridge - Client
 *
 * Runs inside Claude Code sandbox.
 * Translates Stdio MCP messages to GCS objects.
 * Uses Google Cloud Storage instead of S3 (GCS is whitelisted by Anthropic proxy).
 */

import { Storage } from "@google-cloud/storage";
import { randomUUID } from "crypto";

export class GcsMcpBridgeClient {
  constructor(config) {
    this.bucket = config.bucket;
    this.prefix = config.prefix || "mcp-relay";
    this.sessionId = config.sessionId || `session-${Date.now()}-${randomUUID().slice(0, 8)}`;
    this.pollIntervalMs = config.pollIntervalMs || 250;
    this.timeoutMs = config.timeoutMs || 30000;

    // Initialize GCS client
    const storageConfig = {};
    if (config.keyFilename) {
      storageConfig.keyFilename = config.keyFilename;
    } else if (config.credentials) {
      storageConfig.credentials = config.credentials;
    }
    // If no credentials provided, will use Application Default Credentials

    this.storage = new Storage(storageConfig);
    this.bucketHandle = this.storage.bucket(this.bucket);
    this.messageBuffer = "";
  }

  /**
   * Process incoming data from stdin
   */
  async processInput(chunk) {
    this.messageBuffer += chunk.toString();

    const lines = this.messageBuffer.split("\n");
    this.messageBuffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        try {
          const message = JSON.parse(trimmed);
          await this.handleMessage(message);
        } catch (e) {
          console.error(`[GCSBridge] Failed to parse message: ${e.message}`);
        }
      }
    }
  }

  /**
   * Handle a single MCP message
   */
  async handleMessage(message) {
    const requestId = message.id !== undefined ? String(message.id) : `notify-${Date.now()}-${randomUUID().slice(0, 8)}`;
    const gcsPath = `${this.prefix}/requests/${this.sessionId}/${requestId}.json`;

    // Upload request to GCS
    const file = this.bucketHandle.file(gcsPath);
    await file.save(JSON.stringify({
      ...message,
      _bridge: {
        sessionId: this.sessionId,
        requestId: requestId,
        timestamp: new Date().toISOString()
      }
    }), {
      contentType: "application/json"
    });

    // If it's a notification (no id), we don't wait for response
    if (message.id === undefined) {
      return;
    }

    // Poll for response
    const responsePath = `${this.prefix}/responses/${this.sessionId}/${requestId}.json`;
    const response = await this.pollForResponse(responsePath, requestId);

    if (response) {
      process.stdout.write(JSON.stringify(response) + "\n");
    }
  }

  /**
   * Poll GCS for a response
   */
  async pollForResponse(path, requestId) {
    const startTime = Date.now();
    const file = this.bucketHandle.file(path);

    while (Date.now() - startTime < this.timeoutMs) {
      try {
        const [exists] = await file.exists();
        if (exists) {
          const [content] = await file.download();
          const response = JSON.parse(content.toString());

          // Clean up response object
          try {
            await file.delete();
          } catch (deleteErr) {
            console.error(`[GCSBridge] Failed to delete response: ${deleteErr.message}`);
          }

          delete response._bridge;
          return response;
        }
      } catch (e) {
        if (e.code !== 404) {
          console.error(`[GCSBridge] Error polling: ${e.message}`);
        }
      }

      await this.sleep(this.pollIntervalMs);
    }

    // Timeout
    console.error(`[GCSBridge] Timeout waiting for response ${requestId}`);
    return {
      jsonrpc: "2.0",
      id: requestId,
      error: {
        code: -32000,
        message: "GCS Bridge timeout waiting for response"
      }
    };
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  start() {
    console.error(`[GCSBridge] Starting client bridge`);
    console.error(`[GCSBridge] Bucket: ${this.bucket}`);
    console.error(`[GCSBridge] Session: ${this.sessionId}`);

    process.stdin.on("data", (chunk) => this.processInput(chunk));
    process.stdin.on("end", () => {
      console.error("[GCSBridge] Stdin closed, exiting");
      process.exit(0);
    });
  }
}
