"""
WAT Framework Tool Registry

Unified tool discovery and registration system.
Discovers tools from MCP servers, Python modules, and skill definitions.
"""

import ast
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from src.wat.types import (
    ToolCategory,
    ToolDefinition,
    ToolInput,
    ToolOutput,
    CostEstimate,
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Unified registry for all WAT framework tools.

    Provides:
    - Tool discovery from MCP servers, Python modules, and skills
    - Category-based filtering
    - Dependency resolution
    - Tool validation
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[ToolCategory, Set[str]] = {cat: set() for cat in ToolCategory}
        self._tags: Dict[str, Set[str]] = {}
        self._mcp_servers: Dict[str, List[str]] = {}  # server_name -> tool_names

    @property
    def tools(self) -> Dict[str, ToolDefinition]:
        """Get all registered tools."""
        return self._tools.copy()

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool definition to register

        Raises:
            ValueError: If tool with same name already exists
        """
        if tool.name in self._tools:
            existing = self._tools[tool.name]
            if existing.version != tool.version:
                logger.warning(
                    f"Overwriting tool {tool.name} v{existing.version} with v{tool.version}"
                )
            else:
                logger.debug(f"Tool {tool.name} already registered, skipping")
                return

        self._tools[tool.name] = tool
        self._categories[tool.category].add(tool.name)

        for tag in tool.tags:
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(tool.name)

        if tool.mcp_server:
            if tool.mcp_server not in self._mcp_servers:
                self._mcp_servers[tool.mcp_server] = []
            self._mcp_servers[tool.mcp_server].append(tool.name)

        logger.debug(f"Registered tool: {tool.name} (category: {tool.category.value})")

    def unregister(self, name: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            name: Tool name to remove

        Returns:
            True if tool was removed, False if not found
        """
        if name not in self._tools:
            return False

        tool = self._tools.pop(name)
        self._categories[tool.category].discard(name)

        for tag in tool.tags:
            if tag in self._tags:
                self._tags[tag].discard(name)

        if tool.mcp_server and tool.mcp_server in self._mcp_servers:
            self._mcp_servers[tool.mcp_server].remove(name)

        return True

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        """Get all tools in a category."""
        return [self._tools[name] for name in self._categories.get(category, set())]

    def get_by_tag(self, tag: str) -> List[ToolDefinition]:
        """Get all tools with a specific tag."""
        return [self._tools[name] for name in self._tags.get(tag, set())]

    def get_by_mcp_server(self, server: str) -> List[ToolDefinition]:
        """Get all tools from a specific MCP server."""
        return [
            self._tools[name]
            for name in self._mcp_servers.get(server, [])
            if name in self._tools
        ]

    def search(
        self,
        query: str,
        category: Optional[ToolCategory] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ToolDefinition]:
        """
        Search for tools by query string.

        Args:
            query: Search query (matches name, description)
            category: Optional category filter
            tags: Optional tag filters (AND logic)

        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        results = []

        for tool in self._tools.values():
            # Category filter
            if category and tool.category != category:
                continue

            # Tag filter (all tags must match)
            if tags:
                if not all(tag in tool.tags for tag in tags):
                    continue

            # Query match
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                results.append(tool)

        return results

    def validate_dependencies(self, tool_names: List[str]) -> Dict[str, List[str]]:
        """
        Check if all dependencies are satisfied for given tools.

        Args:
            tool_names: List of tool names to check

        Returns:
            Dict mapping tool names to list of missing dependencies
        """
        missing: Dict[str, List[str]] = {}

        for name in tool_names:
            tool = self._tools.get(name)
            if not tool:
                continue

            tool_missing = [dep for dep in tool.dependencies if dep not in self._tools]
            if tool_missing:
                missing[name] = tool_missing

        return missing

    def discover_from_module(
        self,
        module_path: str,
        category: ToolCategory = ToolCategory.GENERAL,
        mcp_server: Optional[str] = None,
    ) -> int:
        """
        Discover tools from a Python module.

        Looks for functions decorated with @tool_definition or
        functions with docstrings in a specific format.

        Args:
            module_path: Python module path (e.g., "src.mcp_gateway.tools.railway")
            category: Default category for discovered tools
            mcp_server: MCP server name if applicable

        Returns:
            Number of tools discovered
        """
        count = 0
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            return 0

        for name, obj in inspect.getmembers(module):
            # Skip private members
            if name.startswith("_"):
                continue

            # Check if it's a function or coroutine
            if not (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)):
                continue

            # Check for @tool_definition decorator (would set __wat_tool__ attribute)
            if hasattr(obj, "__wat_tool__"):
                tool_def = obj.__wat_tool__
                tool_def.handler = obj
                self.register(tool_def)
                count += 1
                continue

            # Try to extract tool definition from docstring
            if obj.__doc__:
                tool_def = self._extract_from_docstring(
                    name, obj, category, mcp_server, module_path
                )
                if tool_def:
                    self.register(tool_def)
                    count += 1

        logger.info(f"Discovered {count} tools from {module_path}")
        return count

    def _extract_from_docstring(
        self,
        name: str,
        func: Callable,
        category: ToolCategory,
        mcp_server: Optional[str],
        source_file: str,
    ) -> Optional[ToolDefinition]:
        """Extract tool definition from function docstring and signature."""
        doc = func.__doc__ or ""
        sig = inspect.signature(func)

        # Extract description (first line of docstring)
        lines = doc.strip().split("\n")
        description = lines[0] if lines else f"Tool: {name}"

        # Extract inputs from function signature
        inputs = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "Any"
            if param.annotation != inspect.Parameter.empty:
                param_type = str(param.annotation)

            required = param.default == inspect.Parameter.empty
            default = None if required else param.default

            # Try to find description in docstring Args section
            param_desc = f"Parameter: {param_name}"
            for line in lines:
                if param_name in line and ":" in line:
                    param_desc = line.split(":", 1)[-1].strip()
                    break

            inputs.append(
                ToolInput(
                    name=param_name,
                    type=param_type,
                    description=param_desc,
                    required=required,
                    default=default,
                )
            )

        # Extract output from return annotation
        output = None
        if sig.return_annotation != inspect.Signature.empty:
            output = ToolOutput(
                type=str(sig.return_annotation),
                description="Return value",
            )

        return ToolDefinition(
            name=name,
            description=description,
            category=category,
            inputs=inputs,
            outputs=output,
            handler=func,
            mcp_server=mcp_server,
            is_async=inspect.iscoroutinefunction(func),
            source_file=source_file,
        )

    def discover_mcp_tools(
        self,
        tools_dir: str,
        category_mapping: Optional[Dict[str, ToolCategory]] = None,
    ) -> int:
        """
        Discover tools from MCP server tool directory.

        Args:
            tools_dir: Path to directory containing MCP tool modules
            category_mapping: Optional mapping of module name to category

        Returns:
            Number of tools discovered
        """
        tools_path = Path(tools_dir)
        if not tools_path.exists():
            logger.warning(f"MCP tools directory not found: {tools_dir}")
            return 0

        category_mapping = category_mapping or {
            "railway": ToolCategory.DEPLOYMENT,
            "n8n": ToolCategory.INTEGRATION,
            "monitoring": ToolCategory.MONITORING,
            "workspace": ToolCategory.WORKSPACE,
            "oauth": ToolCategory.SECURITY,
            "gcloud": ToolCategory.DEPLOYMENT,
            "secrets": ToolCategory.SECURITY,
            "compute": ToolCategory.DEPLOYMENT,
            "storage": ToolCategory.STORAGE,
            "iam": ToolCategory.SECURITY,
        }

        total_count = 0
        for py_file in tools_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            category = category_mapping.get(module_name, ToolCategory.GENERAL)

            # Convert path to module path
            module_path = str(tools_path / module_name).replace("/", ".")
            if module_path.startswith("."):
                module_path = module_path[1:]

            # Determine MCP server name from parent directory
            mcp_server = tools_path.parent.name

            count = self.discover_from_module(module_path, category, mcp_server)
            total_count += count

        return total_count

    def discover_from_skills(self, skills_dir: str) -> int:
        """
        Discover tool-like capabilities from Claude skills.

        Args:
            skills_dir: Path to .claude/skills directory

        Returns:
            Number of skill-tools discovered
        """
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return 0

        count = 0
        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            tool_def = self._parse_skill_file(skill_md)
            if tool_def:
                self.register(tool_def)
                count += 1

        logger.info(f"Discovered {count} skill-tools from {skills_dir}")
        return count

    def _parse_skill_file(self, skill_path: Path) -> Optional[ToolDefinition]:
        """Parse a SKILL.md file into a tool definition."""
        content = skill_path.read_text()
        skill_name = skill_path.parent.name

        # Extract description from first paragraph
        lines = content.split("\n")
        description = ""
        for line in lines:
            if line.strip() and not line.startswith("#") and not line.startswith("-"):
                description = line.strip()
                break

        if not description:
            description = f"Skill: {skill_name}"

        # Determine category from skill name
        category_hints = {
            "doc": ToolCategory.GENERAL,
            "test": ToolCategory.GENERAL,
            "security": ToolCategory.SECURITY,
            "pr": ToolCategory.INTEGRATION,
            "dependency": ToolCategory.GENERAL,
            "changelog": ToolCategory.GENERAL,
            "preflight": ToolCategory.GENERAL,
            "performance": ToolCategory.MONITORING,
            "cost": ToolCategory.MONITORING,
            "research": ToolCategory.DATA,
            "email": ToolCategory.COMMUNICATION,
            "adr": ToolCategory.GENERAL,
            "session": ToolCategory.GENERAL,
        }

        category = ToolCategory.GENERAL
        for hint, cat in category_hints.items():
            if hint in skill_name.lower():
                category = cat
                break

        # Extract triggers as tags
        tags = ["skill"]
        in_triggers = False
        for line in lines:
            if "trigger" in line.lower():
                in_triggers = True
                continue
            if in_triggers and line.strip().startswith("-"):
                tag = line.strip("- `\n").split(",")[0].strip()
                if tag:
                    tags.append(tag)
            elif in_triggers and line.strip() and not line.startswith(" "):
                in_triggers = False

        return ToolDefinition(
            name=f"skill:{skill_name}",
            description=description,
            category=category,
            tags=tags,
            is_async=False,
            source_file=str(skill_path),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export registry to dictionary."""
        return {
            "tools": {name: tool.to_dict() for name, tool in self._tools.items()},
            "categories": {
                cat.value: list(names) for cat, names in self._categories.items()
            },
            "mcp_servers": self._mcp_servers.copy(),
            "total_tools": len(self._tools),
        }

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_tools": len(self._tools),
            "by_category": {
                cat.value: len(names) for cat, names in self._categories.items() if names
            },
            "mcp_servers": list(self._mcp_servers.keys()),
            "tags": list(self._tags.keys()),
        }


def tool_definition(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: ToolCategory = ToolCategory.GENERAL,
    tags: Optional[List[str]] = None,
    cost_estimate: Optional[CostEstimate] = None,
    requires_confirmation: bool = False,
    max_retries: int = 3,
    timeout_seconds: int = 30,
):
    """
    Decorator to mark a function as a WAT tool.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        category: Tool category
        tags: Tool tags for filtering
        cost_estimate: Estimated cost per invocation
        requires_confirmation: Whether to require user confirmation
        max_retries: Maximum retry attempts
        timeout_seconds: Timeout for execution

    Example:
        @tool_definition(
            name="search_places",
            category=ToolCategory.DATA,
            tags=["google", "maps", "search"]
        )
        async def search_places(query: str, location: str = "San Francisco") -> str:
            '''Search for places using Google Places API.'''
            ...
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").split("\n")[0] or f"Tool: {tool_name}"

        # Extract inputs from signature
        sig = inspect.signature(func)
        inputs = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = "Any"
            if param.annotation != inspect.Parameter.empty:
                param_type = str(param.annotation)
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default
            inputs.append(
                ToolInput(
                    name=param_name,
                    type=param_type,
                    description=f"Parameter: {param_name}",
                    required=required,
                    default=default,
                )
            )

        # Extract output
        output = None
        if sig.return_annotation != inspect.Signature.empty:
            output = ToolOutput(
                type=str(sig.return_annotation),
                description="Return value",
            )

        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_desc,
            category=category,
            inputs=inputs,
            outputs=output,
            handler=func,
            tags=tags or [],
            cost_estimate=cost_estimate,
            requires_confirmation=requires_confirmation,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            is_async=inspect.iscoroutinefunction(func),
        )

        func.__wat_tool__ = tool_def
        return func

    return decorator
