"""Port Discovery - Discover service ports from systemd configuration.

This module provides:
- Discovery of portfolio-* services from systemd user units
- Port extraction from service files
- Port probing for running services
- Caching of discovery results
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import httpx

from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoveredPort:
    """A port discovered from systemd services or probing."""

    port: int
    service_name: str  # e.g., "portfolio-backend", "portfolio-frontend"
    service_type: str  # "backend", "frontend", "websocket", "unknown"
    source: str  # "systemd", "probe", "manual"
    description: str | None = None


class PortDiscovery:
    """Discovers ports from systemd user services."""

    # Patterns to extract port from ExecStart command
    PORT_PATTERNS: ClassVar[list[str]] = [
        r"--port[=\s]+(\d+)",  # --port 8000 or --port=8000
        r"-p[=\s]+(\d+)",  # -p 8000 or -p=8000
        r":(\d+)$",  # localhost:8000
    ]

    # Service type mapping based on service name or command
    SERVICE_TYPE_HINTS: ClassVar[dict[str, str]] = {
        "backend": "backend",
        "frontend": "frontend",
        "hatchet": "worker",
        "beat": "scheduler",
        "redis": "cache",
        "companion": "websocket",
    }

    # Common ports to probe if systemd discovery fails
    PROBE_PORTS: ClassVar[list[int]] = [80, 443, 3000, 8000, 8080, 9999]

    def __init__(self) -> None:
        self._systemd_dir = Path.home() / ".config" / "systemd" / "user"
        self._cached_ports: dict[int, DiscoveredPort] | None = None

    def discover_from_systemd(self) -> list[DiscoveredPort]:
        """Parse systemd user services to find portfolio-* services and their ports.

        Returns:
            List of discovered ports with metadata
        """
        discovered: list[DiscoveredPort] = []

        try:
            # List portfolio-* services
            result = subprocess.run(
                ["systemctl", "--user", "list-units", "--type=service", "--all", "--no-pager"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning("systemd_list_failed", stderr=result.stderr)
                return discovered

            # Find portfolio-* services
            service_names = []
            for line in result.stdout.splitlines():
                if "portfolio-" in line and ".service" in line:
                    # Extract service name
                    parts = line.split()
                    if parts:
                        service_name = parts[0].replace(".service", "")
                        service_names.append(service_name)

            logger.info("systemd_services_found", count=len(service_names), services=service_names)

            # Get details for each service
            for service_name in service_names:
                port_info = self._parse_service_file(service_name)
                if port_info:
                    discovered.append(port_info)

        except subprocess.TimeoutExpired:
            logger.warning("systemd_command_timeout")
        except Exception as e:
            logger.error("systemd_discovery_failed", error=str(e), exc_info=True)

        return discovered

    def _parse_service_file(self, service_name: str) -> DiscoveredPort | None:
        """Parse a systemd service file to extract port configuration.

        Args:
            service_name: Name of the systemd service (without .service suffix)

        Returns:
            DiscoveredPort if port found, None otherwise
        """
        service_file = self._systemd_dir / f"{service_name}.service"

        # Resolve symlink if needed
        if service_file.is_symlink():
            service_file = service_file.resolve()

        if not service_file.exists():
            return None

        try:
            content = service_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("service_file_read_failed", service=service_name, error=str(e))
            return None

        port = None
        description = None

        # Extract Description
        desc_match = re.search(r"^Description=(.+)$", content, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()

        # Try to extract port from Environment=PORT=XXXX
        env_match = re.search(r"Environment=[\"']?PORT=(\d+)[\"']?", content)
        if env_match:
            port = int(env_match.group(1))

        # Try to extract port from ExecStart command
        if not port:
            exec_match = re.search(r"^ExecStart=(.+)$", content, re.MULTILINE)
            if exec_match:
                exec_cmd = exec_match.group(1)
                for pattern in self.PORT_PATTERNS:
                    port_match = re.search(pattern, exec_cmd)
                    if port_match:
                        port = int(port_match.group(1))
                        break

        if not port:
            return None

        # Determine service type
        service_type = "unknown"
        name_lower = service_name.lower()
        for hint, stype in self.SERVICE_TYPE_HINTS.items():
            if hint in name_lower:
                service_type = stype
                break

        return DiscoveredPort(
            port=port,
            service_name=service_name,
            service_type=service_type,
            source="systemd",
            description=description,
        )

    async def probe_ports(self, ports: list[int] | None = None) -> list[DiscoveredPort]:
        """Probe common ports to discover running services.

        Args:
            ports: List of ports to probe, defaults to PROBE_PORTS

        Returns:
            List of discovered ports that respond to HTTP
        """
        if ports is None:
            ports = self.PROBE_PORTS

        discovered = []

        async with httpx.AsyncClient(timeout=2) as client:
            for port in ports:
                try:
                    # Try localhost first
                    response = await client.get(f"http://localhost:{port}/")
                    if response.status_code < 500:
                        discovered.append(
                            DiscoveredPort(
                                port=port,
                                service_name=f"unknown-{port}",
                                service_type="unknown",
                                source="probe",
                                description=f"HTTP service on port {port}",
                            )
                        )
                except (httpx.HTTPError, OSError):
                    pass  # Port not responding

        return discovered

    def get_all_ports(self) -> dict[int, DiscoveredPort]:
        """Get all discovered ports, combining systemd and cached results.

        In container mode, returns well-known defaults since systemd is not available
        and cross-container service discovery happens via Docker DNS.

        Returns:
            Dict mapping port number to DiscoveredPort info
        """
        if self._cached_ports is not None:
            return self._cached_ports

        ports = {}

        if Path("/.dockerenv").exists():
            # In Docker, services are on well-known ports via compose networking
            defaults = [
                DiscoveredPort(8000, "portfolio-backend", "backend", "docker"),
                DiscoveredPort(3000, "portfolio-frontend", "frontend", "docker"),
            ]
            for dp in defaults:
                ports[dp.port] = dp
        else:
            # Discover from systemd on bare-metal
            for port_info in self.discover_from_systemd():
                ports[port_info.port] = port_info

        self._cached_ports = ports
        return ports

    def clear_cache(self) -> None:
        """Clear the cached port discovery results."""
        self._cached_ports = None


# Global port discovery instance
_port_discovery = PortDiscovery()


def get_discovered_ports() -> dict[int, DiscoveredPort]:
    """Get all discovered ports from systemd services."""
    return _port_discovery.get_all_ports()


def get_port_for_service(service_type: str) -> int | None:
    """Get port for a specific service type.

    Args:
        service_type: One of "backend", "frontend", "websocket"

    Returns:
        Port number or None if not found
    """
    ports = get_discovered_ports()
    for port, info in ports.items():
        if info.service_type == service_type:
            return port

    # Fallback to defaults if discovery fails
    defaults = {"backend": 8000, "frontend": 3000, "websocket": 9999}
    return defaults.get(service_type)
