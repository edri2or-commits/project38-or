/**
 * GCS MCP Bridge - Server
 *
 * Runs on Railway. Polls GCS for requests, forwards to real MCP server.
 */

import { Storage } from "@google-cloud/storage";
import { spawn } from "child_process";

export class GcsMcpBridgeServer {
  constructor(config) {
    this.bucket = config.bucket;
    this.prefix = config.prefix || "mcp-relay";
    this.pollIntervalMs = config.pollIntervalMs || 500;
    this.mcpUrl = config.mcpUrl;
    this.mcpCommand = config.mcpCommand;
    this.mcpArgs = config.mcpArgs || [];

    const storageConfig = {};
    if (config.keyFilename) {
      storageConfig.keyFilename = config.keyFilename;
    } else if (config.credentials) {
      storageConfig.credentials = config.credentials;
    }

    this.storage = new Storage(storageConfig);
    this.bucketHandle = this.storage.bucket(this.bucket);

    this.running = false;
    this.processedRequests = new Set();
    this.mcpProcess = null;
    this.pendingResponses = new Map();
  }

  startMcpProcess() {
    if (!this.mcpCommand) return;

    console.log(`[GCSBridge Server] Starting MCP: ${this.mcpCommand} ${this.mcpArgs.join(" ")}`);

    this.mcpProcess = spawn(this.mcpCommand, this.mcpArgs, {
      stdio: ["pipe", "pipe", "inherit"]
    });

    this.mcpProcess.stdout.on("data", (data) => {
      this.handleMcpResponse(data.toString());
    });

    this.mcpProcess.on("exit", (code) => {
      console.log(`[GCSBridge Server] MCP process exited with code ${code}`);
      this.running = false;
    });
  }

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
          console.error(`[GCSBridge Server] Parse error: ${e.message}`);
        }
      }
    }
  }

  async sendToMcpProcess(request, sessionId) {
    return new Promise((resolve, reject) => {
      const requestId = request.id !== undefined ? String(request.id) : null;

      if (requestId) {
        this.pendingResponses.set(requestId, { sessionId, resolve });
      }

      const cleanRequest = { ...request };
      delete cleanRequest._bridge;

      this.mcpProcess.stdin.write(JSON.stringify(cleanRequest) + "\n");

      if (!requestId) {
        resolve(null);
      }

      setTimeout(() => {
        if (requestId && this.pendingResponses.has(requestId)) {
          this.pendingResponses.delete(requestId);
          reject(new Error("MCP request timeout"));
        }
      }, 30000);
    });
  }

  async sendToMcpHttp(request, sessionId) {
    const cleanRequest = { ...request };
    delete cleanRequest._bridge;

    const response = await fetch(this.mcpUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

  async processRequest(file) {
    const filePath = file.name;

    try {
      const [content] = await file.download();
      const request = JSON.parse(content.toString());

      const bridgeData = request._bridge || {};
      const sessionId = bridgeData.sessionId || "unknown";
      const requestId = bridgeData.requestId || (request.id !== undefined ? String(request.id) : null);

      console.log(`[GCSBridge Server] Processing ${requestId} from ${sessionId}`);

      let responseData;
      if (this.mcpUrl) {
        responseData = await this.sendToMcpHttp(request, sessionId);
      } else if (this.mcpProcess) {
        responseData = await this.sendToMcpProcess(request, sessionId);
      }

      if (responseData && responseData.response) {
        const responsePath = `${this.prefix}/responses/${sessionId}/${requestId}.json`;
        const responseFile = this.bucketHandle.file(responsePath);
        await responseFile.save(JSON.stringify(responseData.response), {
          contentType: "application/json"
        });
        console.log(`[GCSBridge Server] Response uploaded for ${requestId}`);
      }

      await file.delete();

    } catch (e) {
      console.error(`[GCSBridge Server] Error processing ${filePath}: ${e.message}`);
    }
  }

  async pollForRequests() {
    try {
      const [files] = await this.bucketHandle.getFiles({
        prefix: `${this.prefix}/requests/`
      });

      for (const file of files) {
        if (this.processedRequests.has(file.name)) continue;

        this.processedRequests.add(file.name);
        this.processRequest(file).finally(() => {
          this.processedRequests.delete(file.name);
        });
      }
    } catch (e) {
      console.error(`[GCSBridge Server] Poll error: ${e.message}`);
    }
  }

  async start() {
    console.log(`[GCSBridge Server] Starting`);
    console.log(`[GCSBridge Server] Bucket: ${this.bucket}`);

    this.running = true;

    if (this.mcpCommand) {
      this.startMcpProcess();
    }

    while (this.running) {
      await this.pollForRequests();
      await new Promise(r => setTimeout(r, this.pollIntervalMs));
    }
  }

  stop() {
    this.running = false;
    if (this.mcpProcess) this.mcpProcess.kill();
  }
}
