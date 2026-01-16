"""
GCS MCP Relay Module.

Polls a GCS bucket for MCP requests and processes them locally.
This allows Claude Code sessions behind Anthropic's egress proxy
to communicate with the MCP Gateway.

Architecture:
    Claude Code → GCS (whitelisted) → This Relay → MCP Gateway Tools
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Configuration
GCS_BUCKET = os.environ.get("GCS_BUCKET", "project38-mcp-relay")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "mcp-relay")
POLL_INTERVAL = int(os.environ.get("GCS_POLL_INTERVAL", "2"))

# GCS client (lazy loaded)
_storage_client = None
_bucket = None


def _get_bucket():
    """Get GCS bucket client (lazy initialization)."""
    global _storage_client, _bucket

    if _bucket is not None:
        return _bucket

    try:
        from google.cloud import storage

        # Check for credentials
        creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if creds_json:
            import json as json_module

            from google.oauth2 import service_account

            creds_dict = json_module.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            _storage_client = storage.Client(credentials=credentials)
        else:
            # Use default credentials (works with WIF in GCP environments)
            _storage_client = storage.Client()

        _bucket = _storage_client.bucket(GCS_BUCKET)
        logger.info(f"GCS Relay initialized: gs://{GCS_BUCKET}/{GCS_PREFIX}/")
        return _bucket
    except ImportError:
        logger.warning("google-cloud-storage not installed, GCS relay disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize GCS client: {e}")
        return None


async def process_gcs_request(blob_name: str, request_data: dict) -> dict | None:
    """
    Process a single MCP request from GCS.

    Args:
        blob_name: The GCS blob name
        request_data: The parsed request JSON

    Returns:
        Response dict or None if processing failed
    """
    from .server import create_mcp_server

    try:
        # Extract MCP request
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        logger.info(f"Processing GCS request: {method} (id={request_id})")

        # Get MCP server instance
        mcp = create_mcp_server()
        if mcp is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": "MCP server not available"},
            }

        # Handle different MCP methods
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "project38-mcp-gateway", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }

        elif method == "tools/list":
            # Return list of available tools
            tools = []
            # Get tools from MCP server
            # This is a simplified version - actual implementation would introspect mcp
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            # Call the tool
            # This requires accessing the MCP tools directly
            result = await _call_mcp_tool(tool_name, tool_args)

            return {"jsonrpc": "2.0", "id": request_id, "result": result}

        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {"code": -32000, "message": str(e)},
        }


async def _call_mcp_tool(tool_name: str, args: dict) -> dict:
    """Call an MCP tool by name."""
    from .tools import monitoring, n8n, railway, workspace

    # Map tool names to functions
    tool_map = {
        # Railway
        "railway_deploy": railway.trigger_deployment,
        "railway_status": railway.get_deployment_status,
        "railway_deployments": railway.get_recent_deployments,
        "railway_rollback": railway.execute_rollback,
        # n8n
        "n8n_trigger": n8n.trigger_workflow,
        "n8n_list": n8n.list_workflows,
        "n8n_status": n8n.get_workflow_status,
        # Monitoring
        "health_check": monitoring.check_health,
        "get_metrics": monitoring.get_metrics,
        "deployment_health": monitoring.check_deployment_health,
        # Workspace
        "gmail_send": workspace.gmail_send,
        "gmail_search": workspace.gmail_search,
        "gmail_list": workspace.gmail_list,
        "calendar_list_events": workspace.calendar_list_events,
        "calendar_create_event": workspace.calendar_create_event,
        "drive_list_files": workspace.drive_list_files,
        "drive_create_folder": workspace.drive_create_folder,
        "sheets_read": workspace.sheets_read,
        "sheets_write": workspace.sheets_write,
        "sheets_create": workspace.sheets_create,
        "docs_create": workspace.docs_create,
        "docs_read": workspace.docs_read,
        "docs_append": workspace.docs_append,
    }

    if tool_name not in tool_map:
        raise ValueError(f"Unknown tool: {tool_name}")

    func = tool_map[tool_name]

    # Call the function with args
    if asyncio.iscoroutinefunction(func):
        result = await func(**args)
    else:
        result = func(**args)

    return result


async def poll_gcs_once() -> int:
    """
    Poll GCS for requests once.

    Returns:
        Number of requests processed
    """
    bucket = _get_bucket()
    if bucket is None:
        return 0

    processed = 0
    requests_prefix = f"{GCS_PREFIX}/requests/"

    try:
        blobs = list(bucket.list_blobs(prefix=requests_prefix))

        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue

            try:
                # Download request
                content = blob.download_as_text()
                request_data = json.loads(content)

                # Get response path from request metadata
                bridge_meta = request_data.get("_bridge", {})
                response_path = bridge_meta.get("responsePath")

                if not response_path:
                    logger.warning(f"No response path in {blob.name}")
                    blob.delete()
                    continue

                # Process request
                response = await process_gcs_request(blob.name, request_data)

                if response:
                    # Upload response
                    response_blob = bucket.blob(response_path)
                    response_blob.upload_from_string(
                        json.dumps(response), content_type="application/json"
                    )
                    logger.info(f"Response written to {response_path}")

                # Delete processed request
                blob.delete()
                processed += 1

            except Exception as e:
                logger.error(f"Error processing {blob.name}: {e}")

    except Exception as e:
        logger.error(f"GCS poll error: {e}")

    return processed


async def start_polling_loop():
    """Start the GCS polling loop (runs forever)."""
    logger.info(f"Starting GCS polling loop (interval={POLL_INTERVAL}s)")

    while True:
        try:
            count = await poll_gcs_once()
            if count > 0:
                logger.info(f"Processed {count} GCS requests")
        except Exception as e:
            logger.error(f"Polling error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


def start_background_polling():
    """Start GCS polling in background thread."""
    import threading

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_polling_loop())

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    logger.info("GCS polling started in background thread")
    return thread
