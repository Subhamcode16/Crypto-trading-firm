import httpx
import logging
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger('convex_client')

class AsyncConvexClient:
    """
    Async client for Convex using the HTTP API.
    Provides methods to call mutations and queries.
    """
    
    def __init__(self, deployment_url: Optional[str] = None):
        self.deployment_url = deployment_url or os.getenv("CONVEX_URL")
        if not self.deployment_url:
            logger.error("CONVEX_URL not found in environment")
            # In local dev, npx convex dev usually gives a local URL like http://localhost:3210
            self.deployment_url = "http://localhost:3210"
        
        # Remove trailing slash if present
        if self.deployment_url.endswith("/"):
            self.deployment_url = self.deployment_url[:-1]
            
        self.client = httpx.AsyncClient(timeout=10.0)
        logger.info(f"[CONVEX] Client initialized (URL: {self.deployment_url})")

    async def mutation(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Convex mutation via HTTP POST"""
        url = f"{self.deployment_url}/api/mutation"
        payload = {
            "path": function_name,
            "args": args
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"[CONVEX] Mutation error ({function_name}): {result['error']}")
                return {"success": False, "error": result['error']}
                
            return {"success": True, "data": result.get("value")}
        except Exception as e:
            logger.error(f"[CONVEX] Mutation request failed ({function_name}): {e}")
            return {"success": False, "error": str(e)}

    async def query(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Convex query via HTTP POST"""
        url = f"{self.deployment_url}/api/query"
        payload = {
            "path": function_name,
            "args": args
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"[CONVEX] Query error ({function_name}): {result['error']}")
                return {"success": False, "error": result['error']}
                
            return {"success": True, "data": result.get("value")}
        except Exception as e:
            logger.error(f"[CONVEX] Query request failed ({function_name}): {e}")
            return {"success": False, "error": str(e)}

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
