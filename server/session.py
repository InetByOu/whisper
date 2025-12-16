#!/usr/bin/env python3
"""
Session Management - WHISPER Tunnel Server
"""

import time
import threading
from typing import Optional, Dict, Tuple, Set
from collections import deque
from .utils import get_time_ms, create_session_id

class ClientSession:
    """Client session state"""
    
    def __init__(self, client_addr: Tuple[str, int], session_id: str):
        self.client_addr = client_addr
        self.session_id = session_id
        self.created_time = get_time_ms()
        self.last_active = get_time_ms()
        self.last_seq = 0
        self.is_active = True
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.probe_port = client_addr[1]  # Original probe port
        
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active = get_time_ms()
    
    def is_expired(self, timeout_ms: int = 30000) -> bool:
        """Check if session is expired"""
        return (get_time_ms() - self.last_active) > timeout_ms
    
    def get_stats(self) -> Dict:
        """Get session statistics"""
        return {
            "session_id": self.session_id,
            "client_addr": f"{self.client_addr[0]}:{self.client_addr[1]}",
            "uptime": (get_time_ms() - self.created_time) // 1000,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "is_active": self.is_active
        }

class SessionManager:
    """Manage client sessions"""
    
    def __init__(self, timeout: int = 30):
        self.sessions: Dict[str, ClientSession] = {}  # session_id -> session
        self.addr_to_session: Dict[Tuple[str, int], str] = {}  # addr -> session_id
        self.timeout = timeout * 1000  # Convert to ms
        self.lock = threading.RLock()
        self.max_sessions = 1000
    
    def create_session(self, client_addr: Tuple[str, int]) -> Optional[ClientSession]:
        """Create new session for client"""
        with self.lock:
            # Check if session already exists
            if client_addr in self.addr_to_session:
                session_id = self.addr_to_session[client_addr]
                if session_id in self.sessions:
                    return self.sessions[session_id]
            
            # Check max sessions
            if len(self.sessions) >= self.max_sessions:
                self._cleanup_expired(force=True)
                if len(self.sessions) >= self.max_sessions:
                    return None
            
            # Create new session
            session_id = create_session_id(client_addr)
            session = ClientSession(client_addr, session_id)
            
            self.sessions[session_id] = session
            self.addr_to_session[client_addr] = session_id
            
            print(f"New session created: {session_id} for {client_addr[0]}:{client_addr[1]}")
            return session
    
    def get_session(self, session_id: str) -> Optional[ClientSession]:
        """Get session by ID"""
        with self.lock:
            return self.sessions.get(session_id)
    
    def get_session_by_addr(self, client_addr: Tuple[str, int]) -> Optional[ClientSession]:
        """Get session by client address"""
        with self.lock:
            session_id = self.addr_to_session.get(client_addr)
            if session_id:
                return self.sessions.get(session_id)
            return None
    
    def update_session_activity(self, session_id: str):
        """Update session activity timestamp"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.update_activity()
    
    def remove_session(self, session_id: str):
        """Remove session"""
        with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session.client_addr in self.addr_to_session:
                    del self.addr_to_session[session.client_addr]
                del self.sessions[session_id]
                print(f"Session removed: {session_id}")
    
    def _cleanup_expired(self, force: bool = False):
        """Cleanup expired sessions"""
        with self.lock:
            expired = []
            now = get_time_ms()
            
            for session_id, session in self.sessions.items():
                if session.is_expired(self.timeout):
                    expired.append(session_id)
            
            for session_id in expired:
                self.remove_session(session_id)
            
            if expired and (force or len(expired) > 0):
                print(f"Cleaned up {len(expired)} expired sessions")
    
    def cleanup(self):
        """Periodic cleanup"""
        self._cleanup_expired()
    
    def get_all_sessions(self) -> Dict[str, Dict]:
        """Get all session stats"""
        with self.lock:
            return {sid: session.get_stats() for sid, session in self.sessions.items()}
