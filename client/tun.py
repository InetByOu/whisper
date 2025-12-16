#!/usr/bin/env python3
"""
Client TUN interface
"""

import os
import fcntl
import struct
import threading
import queue
from typing import Optional, Callable

from .config import config

# Linux TUN/TAP constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

class TUNClient:
    """Client TUN interface"""
    
    def __init__(self):
        self.tun_fd: Optional[int] = None
        self.tun_name = config.tun_name
        self.running = False
        self.read_queue = queue.Queue()
        self.write_queue = queue.Queue()
        self.packet_handler: Optional[Callable] = None
        self.read_thread: Optional[threading.Thread] = None
        self.write_thread: Optional[threading.Thread] = None
    
    def create(self) -> bool:
        """Create TUN interface"""
        try:
            # Open TUN device
            self.tun_fd = os.open('/dev/net/tun', os.O_RDWR)
            
            # Setup TUN interface
            ifr = struct.pack('16sH', self.tun_name.encode(), IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.tun_fd, TUNSETIFF, ifr)
            
            # Set non-blocking
            flags = fcntl.fcntl(self.tun_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.tun_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Set MTU
            os.system(f"ip link set {self.tun_name} mtu {config.tun_mtu}")
            
            # Configure IP and routing
            os.system(f"ip addr add {config.tun_ip}/{config.tun_netmask} dev {self.tun_name}")
            os.system(f"ip link set {self.tun_name} up")
            
            # Add route for server (keep direct connection)
            os.system(f"ip route add {config.server_ip}/32 via $(ip route | grep default | awk '{{print $3}}')")
            
            # Change default route to TUN
            os.system(f"ip route del default 2>/dev/null")
            os.system(f"ip route add default via {config.tun_gateway} dev {self.tun_name}")
            
            return True
            
        except Exception as e:
            print(f"Error creating TUN: {e}")
            return False
    
    def set_packet_handler(self, handler: Callable):
        """Set packet handler"""
        self.packet_handler = handler
    
    def start(self):
        """Start TUN interface"""
        if not self.tun_fd:
            if not self.create():
                raise RuntimeError("Failed to create TUN interface")
        
        self.running = True
        
        # Start read thread
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        
        # Start write thread
        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()
    
    def stop(self):
        """Stop TUN interface"""
        self.running = False
        
        if self.read_thread:
            self.read_thread.join(timeout=2)
        
        if self.write_thread:
            self.write_thread.join(timeout=2)
        
        # Restore default route
        os.system(f"ip route del default dev {self.tun_name} 2>/dev/null")
        default_gw = os.popen("ip route | grep default | head -1").read().strip()
        if default_gw:
            os.system(f"ip route add {default_gw}")
        
        # Remove TUN
        if self.tun_fd:
            os.close(self.tun_fd)
            self.tun_fd = None
        
        os.system(f"ip link delete {self.tun_name} 2>/dev/null")
    
    def _read_loop(self):
        """Read packets from TUN"""
        while self.running:
            try:
                # Read packet
                ready, _, _ = select.select([self.tun_fd], [], [], 0.1)
                if ready:
                    packet = os.read(self.tun_fd, config.max_packet_size)
                    if packet and self.packet_handler:
                        self.packet_handler(packet)
            except (BlockingIOError, InterruptedError):
                pass
            except Exception as e:
                print(f"Error in TUN read loop: {e}")
                time.sleep(0.1)
    
    def _write_loop(self):
        """Write packets to TUN"""
        while self.running:
            try:
                packet = self.write_queue.get(timeout=0.1)
                if packet and self.tun_fd:
                    os.write(self.tun_fd, packet)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error writing to TUN: {e}")
    
    def write_packet(self, packet: bytes):
        """Queue packet for writing to TUN"""
        self.write_queue.put(packet)
