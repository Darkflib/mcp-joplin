"""Health check and connection validation middleware."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""

    name: str
    status: HealthStatus
    message: str
    response_time_ms: float | None = None
    last_checked: float | None = None
    details: dict[str, Any] | None = None


class HealthChecker:
    """Performs comprehensive health checks for the MCP server."""

    def __init__(self, connection_manager=None, rate_limiter=None):
        """Initialize health checker with dependencies."""
        self.connection_manager = connection_manager
        self.rate_limiter = rate_limiter
        self.last_health_check: float | None = None
        self.cached_health_status: dict[str, Any] | None = None
        self.cache_ttl = 30.0  # Cache health status for 30 seconds

    async def check_health(self, include_details: bool = True) -> dict[str, Any]:
        """Perform comprehensive health check."""
        current_time = time.time()

        # Use cached result if recent
        if (
            self.cached_health_status
            and self.last_health_check
            and current_time - self.last_health_check < self.cache_ttl
        ):
            logger.debug("Returning cached health status")
            return self.cached_health_status

        logger.info("Performing health check")
        start_time = current_time

        # Perform all health checks concurrently
        checks = await asyncio.gather(
            self._check_joplin_connection(),
            self._check_rate_limiter(),
            self._check_system_resources(),
            return_exceptions=True,
        )

        # Process results
        health_checks = []
        for check_result in checks:
            if isinstance(check_result, Exception):
                health_checks.append(
                    HealthCheck(
                        name="unknown",
                        status=HealthStatus.UNKNOWN,
                        message=f"Health check failed: {str(check_result)}",
                    )
                )
            else:
                health_checks.append(check_result)

        # Determine overall health status
        overall_status = self._determine_overall_status(health_checks)

        # Build response
        total_time = (time.time() - start_time) * 1000

        health_response = {
            "status": overall_status.value,
            "timestamp": time.time(),
            "response_time_ms": round(total_time, 2),
            "checks": {},
        }

        # Add individual check results
        for check in health_checks:
            health_response["checks"][check.name] = {
                "status": check.status.value,
                "message": check.message,
                "response_time_ms": check.response_time_ms,
                "last_checked": check.last_checked,
            }

            if include_details and check.details:
                health_response["checks"][check.name]["details"] = check.details

        # Cache result
        self.cached_health_status = health_response
        self.last_health_check = current_time

        logger.info(
            "Health check completed",
            extra={
                "overall_status": overall_status.value,
                "total_time_ms": total_time,
                "checks_count": len(health_checks),
            },
        )

        return health_response

    async def _check_joplin_connection(self) -> HealthCheck:
        """Check Joplin connection health."""
        start_time = time.time()

        try:
            if not self.connection_manager:
                return HealthCheck(
                    name="joplin_connection",
                    status=HealthStatus.UNKNOWN,
                    message="Connection manager not available",
                    response_time_ms=0,
                    last_checked=start_time,
                )

            # Perform connection health check
            conn_health = await self.connection_manager.health_check()
            response_time = (time.time() - start_time) * 1000

            if conn_health.get("connected", False):
                status = HealthStatus.HEALTHY
                message = "Joplin connection healthy"
            else:
                status = HealthStatus.UNHEALTHY
                message = conn_health.get("error", "Connection failed")

            return HealthCheck(
                name="joplin_connection",
                status=status,
                message=message,
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
                details=conn_health,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="joplin_connection",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection check failed: {str(e)}",
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
            )

    async def _check_rate_limiter(self) -> HealthCheck:
        """Check rate limiter health."""
        start_time = time.time()

        try:
            if not self.rate_limiter:
                return HealthCheck(
                    name="rate_limiter",
                    status=HealthStatus.UNKNOWN,
                    message="Rate limiter not available",
                    response_time_ms=0,
                    last_checked=start_time,
                )

            # Get rate limiter status
            rate_status = await self.rate_limiter.get_status()
            response_time = (time.time() - start_time) * 1000

            # Determine status based on utilization
            utilization = rate_status.get("utilization_percent", 0)
            tokens_available = rate_status.get("tokens_available", 0)

            if utilization > 90 or tokens_available == 0:
                status = HealthStatus.DEGRADED
                message = f"Rate limiter at {utilization}% utilization"
            elif utilization > 70:
                status = HealthStatus.DEGRADED
                message = f"Rate limiter at {utilization}% utilization"
            else:
                status = HealthStatus.HEALTHY
                message = f"Rate limiter healthy ({utilization}% utilization)"

            return HealthCheck(
                name="rate_limiter",
                status=status,
                message=message,
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
                details=rate_status,
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="rate_limiter",
                status=HealthStatus.UNHEALTHY,
                message=f"Rate limiter check failed: {str(e)}",
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
            )

    async def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage."""
        start_time = time.time()

        try:
            import os

            import psutil

            # Get current process
            process = psutil.Process(os.getpid())

            # Memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # CPU usage (over short interval)
            cpu_percent = process.cpu_percent(interval=0.1)

            # File descriptors (Unix only)
            fd_count = None
            try:
                fd_count = process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                pass  # Not available on all platforms

            response_time = (time.time() - start_time) * 1000

            # Determine status based on resource usage
            status = HealthStatus.HEALTHY
            issues = []

            if memory_mb > 100:  # More than 100MB
                status = HealthStatus.DEGRADED
                issues.append(f"High memory usage: {memory_mb:.1f}MB")

            if cpu_percent > 80:  # More than 80% CPU
                status = HealthStatus.DEGRADED
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")

            if fd_count and fd_count > 100:  # Many open file descriptors
                status = HealthStatus.DEGRADED
                issues.append(f"Many open FDs: {fd_count}")

            message = "System resources healthy" if not issues else "; ".join(issues)

            details = {
                "memory_mb": round(memory_mb, 1),
                "cpu_percent": round(cpu_percent, 1),
            }

            if fd_count is not None:
                details["file_descriptors"] = fd_count

            return HealthCheck(
                name="system_resources",
                status=status,
                message=message,
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
                details=details,
            )

        except ImportError:
            # psutil not available
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message="System monitoring not available (psutil not installed)",
                response_time_ms=0,
                last_checked=start_time,
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Resource check failed: {str(e)}",
                response_time_ms=round(response_time, 2),
                last_checked=start_time,
            )

    def _determine_overall_status(self, checks: list[HealthCheck]) -> HealthStatus:
        """Determine overall health status from individual checks."""
        if not checks:
            return HealthStatus.UNKNOWN

        # Count statuses
        status_counts = {}
        for check in checks:
            status_counts[check.status] = status_counts.get(check.status, 0) + 1

        # Determine overall status
        if status_counts.get(HealthStatus.UNHEALTHY, 0) > 0:
            return HealthStatus.UNHEALTHY
        elif status_counts.get(HealthStatus.DEGRADED, 0) > 0:
            return HealthStatus.DEGRADED
        elif status_counts.get(HealthStatus.UNKNOWN, 0) > 0:
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.HEALTHY

    async def check_readiness(self) -> bool:
        """Check if server is ready to handle requests."""
        try:
            health = await self.check_health(include_details=False)
            status = health.get("status")

            # Server is ready if healthy or degraded (but not unhealthy or unknown)
            return status in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]

        except Exception as e:
            logger.error("Readiness check failed", extra={"error": str(e)})
            return False

    def invalidate_cache(self) -> None:
        """Invalidate cached health status."""
        self.cached_health_status = None
        self.last_health_check = None
        logger.debug("Health check cache invalidated")
