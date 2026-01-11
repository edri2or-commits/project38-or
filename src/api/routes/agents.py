"""Agent CRUD endpoints for Agent Platform API.

This module provides REST API endpoints for creating, reading, updating,
and deleting agents. It integrates the Agent Factory (Phase 3.2) to generate
agents from natural language descriptions.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.factory.generator import estimate_cost, generate_agent_code
from src.factory.ralph_loop import get_loop_summary, ralph_wiggum_loop

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class AgentCreateRequest(BaseModel):
    """Request model for creating a new agent.

    Attributes:
        description: Natural language description of agent functionality
        name: Optional agent name (generated from description if not provided)
        created_by: Optional user identifier
        strict_validation: Enable strict validation (pydocstyle)
    """

    description: str = Field(
        ..., min_length=10, max_length=2000, description="Agent functionality description"
    )
    name: str | None = Field(None, max_length=255, description="Agent name")
    created_by: str | None = Field(None, max_length=255, description="Creator ID")
    strict_validation: bool = Field(True, description="Enable strict validation")


class AgentResponse(BaseModel):
    """Response model for agent operations.

    Attributes:
        id: Agent unique identifier
        name: Agent name
        description: Agent description
        code: Generated Python code
        status: Agent status
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: Creator identifier
        config: JSON configuration
    """

    id: int
    name: str
    description: str
    code: str
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    config: str | None = None


class AgentCreateResponse(AgentResponse):
    """Extended response for agent creation.

    Includes generation metrics like cost and iterations.

    Attributes:
        generation_cost: Estimated cost in USD
        iterations: Number of fix iterations
        tokens_used: Total tokens consumed
    """

    generation_cost: float = Field(..., description="Estimated generation cost (USD)")
    iterations: int = Field(..., description="Ralph loop iterations")
    tokens_used: int = Field(..., description="Total tokens used")


class AgentUpdateRequest(BaseModel):
    """Request model for updating an agent.

    Attributes:
        name: New agent name
        description: New description
        code: Updated code
        status: New status
        config: Updated configuration
    """

    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    code: str | None = None
    status: str | None = Field(None, max_length=50)
    config: str | None = None


class AgentExecuteRequest(BaseModel):
    """Request model for executing an agent.

    Attributes:
        config: Execution-specific configuration (JSON)
    """

    config: dict | None = Field(None, description="Execution configuration")


class AgentExecuteResponse(BaseModel):
    """Response model for agent execution.

    Attributes:
        agent_id: Agent identifier
        status: Execution status
        result: Execution result
        started_at: Execution start time
        completed_at: Execution completion time
    """

    agent_id: int
    status: str
    result: dict | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


@router.post(
    "/agents",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(request: AgentCreateRequest) -> AgentCreateResponse:
    """Create a new agent from natural language description.

    This endpoint implements the core Agent Factory functionality:
    1. Generate Python code from description using Claude Sonnet 4.5
    2. Validate and fix code using Ralph Wiggum Loop
    3. Save to database with generated code

    Args:
        request: Agent creation request with description and metadata

    Returns:
        AgentCreateResponse: Created agent with generation metrics

    Raises:
        HTTPException: 500 if generation fails, 422 if validation fails

    Example:
        >>> payload = {
        ...     "description": "Monitor Tesla stock and alert on 5% increase",
        ...     "name": "Stock Monitor"
        ... }
        >>> response = await create_agent(payload)
        >>> print(f"Created agent {response.id} in {response.iterations} iterations")
    """
    logger.info("Creating agent from description: %s", request.description[:100])

    try:
        # Step 1: Generate initial code with Claude
        generation_result = await generate_agent_code(
            description=request.description,
            max_tokens=4096,
        )

        logger.info(
            "Generated code (%d tokens)", generation_result["tokens_used"]
        )

        # Step 2: Run Ralph Wiggum Loop to fix any issues
        loop_result = await ralph_wiggum_loop(
            code=generation_result["code"],
            strict=request.strict_validation,
            max_iterations=5,
        )

        logger.info("Ralph loop completed:\n%s", get_loop_summary(loop_result))

        if not loop_result["passed"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Failed to generate valid code",
                    "errors": loop_result["errors"],
                    "warnings": loop_result["warnings"],
                },
            )

        # Step 3: Generate agent name if not provided
        agent_name = request.name
        if not agent_name:
            # Extract first few words from description
            words = request.description.split()[:5]
            agent_name = " ".join(words) + " Agent"

        # Step 4: Save to database (TODO: Implement database layer)
        # For now, return mock response
        # In Phase 3.3, this will actually save to PostgreSQL
        agent_id = 1  # Mock ID

        # Calculate cost
        total_tokens = generation_result["tokens_used"] + loop_result.get(
            "tokens_used", 0
        )
        cost = estimate_cost(total_tokens)

        logger.info(
            "Agent created successfully (ID: %d, Cost: $%.4f)", agent_id, cost
        )

        return AgentCreateResponse(
            id=agent_id,
            name=agent_name,
            description=request.description,
            code=loop_result["code"],
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by=request.created_by,
            config=None,
            generation_cost=cost,
            iterations=loop_result["iterations"],
            tokens_used=total_tokens,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Agent creation failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent creation failed: {str(e)}",
        ) from e


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    status: str | None = None,
    created_by: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AgentResponse]:
    """List all agents with optional filtering.

    Args:
        status: Filter by agent status (active/paused/stopped/error)
        created_by: Filter by creator identifier
        limit: Maximum number of results (default: 100, max: 1000)
        offset: Pagination offset (default: 0)

    Returns:
        List[AgentResponse]: List of agents

    Example:
        >>> agents = await list_agents(status="active", limit=10)
        >>> print(f"Found {len(agents)} active agents")
    """
    logger.info(
        "Listing agents (status=%s, created_by=%s, limit=%d, offset=%d)",
        status,
        created_by,
        limit,
        offset,
    )

    # TODO: Implement database query
    # For now, return empty list
    return []


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int) -> AgentResponse:
    """Get a specific agent by ID.

    Args:
        agent_id: Agent unique identifier

    Returns:
        AgentResponse: Agent details

    Raises:
        HTTPException: 404 if agent not found

    Example:
        >>> agent = await get_agent(1)
        >>> print(agent.name)
    """
    logger.info("Getting agent %d", agent_id)

    # TODO: Implement database query
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent {agent_id} not found",
    )


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int, request: AgentUpdateRequest
) -> AgentResponse:
    """Update an existing agent.

    Args:
        agent_id: Agent unique identifier
        request: Update request with fields to change

    Returns:
        AgentResponse: Updated agent details

    Raises:
        HTTPException: 404 if agent not found

    Example:
        >>> response = await update_agent(
        ...     1,
        ...     AgentUpdateRequest(status="paused")
        ... )
        >>> print(response.status)
        paused
    """
    logger.info("Updating agent %d", agent_id)

    # TODO: Implement database update
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent {agent_id} not found",
    )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int) -> None:
    """Delete an agent.

    Args:
        agent_id: Agent unique identifier

    Raises:
        HTTPException: 404 if agent not found

    Example:
        >>> await delete_agent(1)
    """
    logger.info("Deleting agent %d", agent_id)

    # TODO: Implement database deletion
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent {agent_id} not found",
    )


@router.post(
    "/agents/{agent_id}/execute",
    response_model=AgentExecuteResponse,
)
async def execute_agent(
    agent_id: int, request: AgentExecuteRequest
) -> AgentExecuteResponse:
    """Trigger manual execution of an agent.

    Args:
        agent_id: Agent unique identifier
        request: Execution configuration

    Returns:
        AgentExecuteResponse: Execution result

    Raises:
        HTTPException: 404 if agent not found, 500 if execution fails

    Example:
        >>> response = await execute_agent(
        ...     1,
        ...     AgentExecuteRequest(config={"symbol": "TSLA"})
        ... )
        >>> print(response.status)
        success
    """
    logger.info("Executing agent %d", agent_id)

    # TODO: Implement agent execution
    # This will be implemented in Phase 3.3 (Agent Harness)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Agent execution not yet implemented (Phase 3.3)",
    )
