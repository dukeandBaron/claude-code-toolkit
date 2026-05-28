"""
AgentLink Protocol - LAN Discovery

Provides three discovery mechanisms:
1. mDNS/DNS-SD (primary) - automatic discovery on local network
2. UDP Broadcast (fallback) - simple broadcast discovery
3. Manual pairing - direct connection by IP:port

Usage:
    # Register this agent for discovery
    discovery = AgentDiscovery(name="My Agent", port=7600)
    await discovery.start()
    
    # Browse for other agents
    agents = await discovery.browse(timeout=5.0)
    for agent in agents:
        print(f"Found: {agent['name']} at {agent['address']}:{agent['port']}")
"""

import asyncio
import json
import logging
import socket
import time
import uuid
from typing import Optional

logger = logging.getLogger("agentlink.discovery")

# mDNS service type for AgentLink
SERVICE_TYPE = "_agentlink._tcp.local."
BROADCAST_PORT = 7602


class AgentDiscovery:
    """
    LAN discovery for AgentLink agents.
    
    Supports mDNS (via zeroconf) and UDP broadcast fallback.
    """
    
    def __init__(
        self,
        name: str = "AgentLink Agent",
        agent_id: str = None,
        agent_type: str = "custom",
        port: int = 7600,
        host: str = None,
    ):
        self.name = name
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type
        self.port = port
        self.host = host or self._get_local_ip()
        
        self._zeroconf = None
        self._service_info = None
        self._broadcast_task = None
        self._broadcast_socket = None
        self._found_agents: dict[str, dict] = {}
        self._running = False
    
    @staticmethod
    def _get_local_ip() -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    async def start(self):
        """Start broadcasting this agent's presence."""
        self._running = True
        
        # Try mDNS first
        try:
            await self._start_mdns()
            logger.info(f"[DISCOVERY] mDNS registered: {self.name}")
        except ImportError:
            logger.warning("[DISCOVERY] zeroconf not available, using UDP broadcast only")
        
        # Always start UDP broadcast as backup
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info(f"[DISCOVERY] UDP broadcast started on port {BROADCAST_PORT}")
    
    async def stop(self):
        """Stop broadcasting and clean up."""
        self._running = False
        
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        
        if self._zeroconf:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
            except Exception:
                pass
        
        if self._broadcast_socket:
            self._broadcast_socket.close()
        
        logger.info("[DISCOVERY] Stopped")
    
    async def _start_mdns(self):
        """Register via mDNS/DNS-SD."""
        try:
            from zeroconf import ServiceInfo, Zeroconf
        except ImportError:
            raise ImportError(
                "zeroconf library required for mDNS. "
                "Install with: pip install zeroconf"
            )
        
        info = ServiceInfo(
            SERVICE_TYPE,
            f"{self.name}._agentlink._tcp.local.",
            addresses=[socket.inet_aton(self.host)],
            port=self.port,
            properties={
                "id": self.agent_id,
                "type": self.agent_type,
                "version": "1.0",
                "name": self.name,
            },
        )
        
        self._zeroconf = Zeroconf()
        self._service_info = info
        await asyncio.get_event_loop().run_in_executor(
            None, self._zeroconf.register_service, info
        )
    
    async def _broadcast_loop(self):
        """Periodically broadcast this agent's presence via UDP."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        self._broadcast_socket = sock
        
        announcement = json.dumps({
            "type": "agentlink.discovery",
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "ws_port": self.port,
            "address": self.host,
            "timestamp": time.time(),
        }).encode()
        
        while self._running:
            try:
                sock.sendto(announcement, ("255.255.255.255", BROADCAST_PORT))
                await asyncio.sleep(5)  # Broadcast every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[DISCOVERY] Broadcast error: {e}")
                await asyncio.sleep(5)
    
    async def browse(self, timeout: float = 5.0) -> list[dict]:
        """
        Browse for other AgentLink agents on the network.
        
        Returns a list of discovered agents with their connection info.
        """
        self._found_agents.clear()
        
        # Try mDNS browse
        mdns_agents = await self._browse_mdns(timeout)
        
        # Try UDP listen
        udp_agents = await self._browse_udp(timeout)
        
        # Merge results (mDNS takes priority)
        all_agents = {}
        for agent in mdns_agents:
            all_agents[agent["agent_id"]] = agent
        for agent in udp_agents:
            if agent["agent_id"] not in all_agents:
                all_agents[agent["agent_id"]] = agent
        
        # Filter out ourselves
        result = [
            agent for agent in all_agents.values()
            if agent["agent_id"] != self.agent_id
        ]
        
        return result
    
    async def _browse_mdns(self, timeout: float) -> list[dict]:
        """Browse for agents via mDNS."""
        try:
            from zeroconf import Zeroconf, ServiceBrowser
        except ImportError:
            return []
        
        found = []
        
        def on_service(zc, svc_type, name, state_change):
            if name == f"{self.name}._agentlink._tcp.local.":
                return  # Skip ourselves
            
            info = zc.get_service_info(svc_type, name)
            if info:
                agent = {
                    "agent_id": info.properties.get("id", b"unknown").decode(),
                    "agent_name": info.properties.get("name", name).decode(),
                    "agent_type": info.properties.get("type", b"unknown").decode(),
                    "address": socket.inet_ntoa(info.addresses[0]) if info.addresses else "unknown",
                    "port": info.port,
                    "discovery_method": "mdns",
                }
                found.append(agent)
        
        zc = Zeroconf()
        browser = ServiceBrowser(zc, SERVICE_TYPE, handlers=[on_service])
        
        await asyncio.sleep(timeout)
        
        browser.cancel()
        zc.close()
        
        return found
    
    async def _browse_udp(self, timeout: float) -> list[dict]:
        """Listen for UDP broadcast announcements."""
        found = {}
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        
        try:
            sock.bind(("0.0.0.0", BROADCAST_PORT))
        except OSError:
            # Port might be in use by our own broadcast
            try:
                sock.bind(("", BROADCAST_PORT + 1))
            except OSError:
                return []
        
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                data, addr = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: sock.recvfrom(4096)
                )
                
                announcement = json.loads(data.decode())
                
                if announcement.get("type") == "agentlink.discovery":
                    agent_id = announcement.get("agent_id", "")
                    
                    # Skip ourselves
                    if agent_id == self.agent_id:
                        continue
                    
                    if agent_id not in found:
                        agent = {
                            "agent_id": agent_id,
                            "agent_name": announcement.get("agent_name", "unknown"),
                            "agent_type": announcement.get("agent_type", "unknown"),
                            "address": announcement.get("address", addr[0]),
                            "port": announcement.get("ws_port", 7600),
                            "discovery_method": "udp_broadcast",
                        }
                        found[agent_id] = agent
                        logger.info(f"[DISCOVERY] Found agent via UDP: {agent['agent_name']}")
            
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning(f"[DISCOVERY] UDP browse error: {e}")
                break
        
        sock.close()
        return list(found.values())
    
    def get_connection_url(self, agent: dict) -> str:
        """Get the WebSocket URL for connecting to a discovered agent."""
        return f"ws://{agent['address']}:{agent['port']}"


async def discover_agents(timeout: float = 5.0) -> list[dict]:
    """
    Convenience function to discover agents on the local network.
    
    Returns a list of discovered agents with connection info.
    """
    discovery = AgentDiscovery(name="Discovery Probe")
    return await discovery.browse(timeout)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentLink LAN Discovery")
    parser.add_argument("--action", choices=["browse", "announce"], default="browse")
    parser.add_argument("--name", default="AgentLink Agent", help="Agent name")
    parser.add_argument("--port", type=int, default=7600, help="Agent WebSocket port")
    parser.add_argument("--timeout", type=float, default=10.0, help="Browse timeout")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        if args.action == "browse":
            print(f"Scanning for AgentLink agents on local network...")
            print(f"Timeout: {args.timeout}s\n")
            
            agents = await discover_agents(timeout=args.timeout)
            
            if agents:
                print(f"Found {len(agents)} agent(s):\n")
                for i, agent in enumerate(agents, 1):
                    print(f"  {i}. {agent['agent_name']}")
                    print(f"     ID: {agent['agent_id']}")
                    print(f"     Type: {agent['agent_type']}")
                    print(f"     Address: {agent['address']}:{agent['port']}")
                    print(f"     Discovered via: {agent['discovery_method']}")
                    print()
            else:
                print("No agents found. Make sure the other agent is running.")
        
        elif args.action == "announce":
            discovery = AgentDiscovery(
                name=args.name,
                port=args.port,
            )
            await discovery.start()
            print(f"Announcing as '{args.name}' on port {args.port}")
            print("Press Ctrl+C to stop\n")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await discovery.stop()
                print("\nStopped.")
    
    asyncio.run(main())
