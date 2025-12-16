#!/usr/bin/env python3
"""
Rate Limiting - WHISPER Tunnel Server
"""

import time
from typing import Dict, Tuple
from collections import deque

class RateLimiter:
    """Rate limiter per session"""
    
    def __init__(self, max_rate: int = 100, window: float = 1.0):
        """
        Args:
            max_rate: Maximum packets per second
            window: Time window in seconds
        """
        self.max_rate = max_rate
        self.window = window
        self.counters: Dict[str, deque] = {}
    
    def check_limit(self, session_id: str) -> bool:
        """Check if session is within rate limit"""
        now = time.time()
        
        # Initialize deque for new sessions
        if session_id not in self.counters:
            self.counters[session_id] = deque()
        
        # Clean old timestamps
        timestamps = self.counters[session_id]
        while timestamps and (now - timestamps[0]) > self.window:
            timestamps.popleft()
        
        # Check rate
        if len(timestamps) >= self.max_rate:
            return False
        
        # Add current timestamp
        timestamps.append(now)
        
        # Cleanup old sessions (optional)
        if len(timestamps) == 0:
            del self.counters[session_id]
        
        return True
    
    def cleanup(self):
        """Cleanup old entries"""
        now = time.time()
        to_remove = []
        
        for session_id, timestamps in self.counters.items():
            # Remove old timestamps
            while timestamps and (now - timestamps[0]) > self.window:
                timestamps.popleft()
            
            # Mark empty deques for removal
            if not timestamps:
                to_remove.append(session_id)
        
        # Remove empty entries
        for session_id in to_remove:
            del self.counters[session_id]
