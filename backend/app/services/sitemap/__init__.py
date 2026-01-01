"""Sitemap package - Discovery and health monitoring for all endpoints.

This package provides:
- SitemapService: Main coordinator for discovery and health checks
- SitemapDiscoveryService: Endpoint discovery from various sources
- SitemapHealthCheckService: Health monitoring and status tracking
"""

from .sitemap_service import SitemapService

__all__ = ["SitemapService", "get_sitemap_service"]


# Factory function for service instantiation
def get_sitemap_service() -> SitemapService:
    """Get a SitemapService instance.

    Returns:
        SitemapService instance
    """
    return SitemapService()
