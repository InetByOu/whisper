#!/usr/bin/env python3
"""
UDTUN Server Utilities
"""

import os
import sys
import time
import struct
import logging
import ipaddress
from typing import Optional, Tuple

def setup_logging(log_file: str, log_level: str = "INFO") -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger("udtun-server")
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Set level
    level = getattr(logging, log_level.upper())
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    return logger

def validate_ipv4_packet(packet: bytes) -> bool:
    """Validate IPv4 packet"""
    if len(packet) < 20:
        return False
    
    try:
        # Check IP version (must be IPv4)
        version = packet[0] >> 4
        if version != 4:
            return False
        
        # Check IHL (Internet Header Length)
        ihl = packet[0] & 0x0F
        if ihl < 5:
            return False
        
        # Check total length
        total_length = struct.unpack('!H', packet[2:4])[0]
        if total_length < 20 or total_length > 65535:
            return False
        
        # Verify packet length matches total length
        if len(packet) < total_length:
            return False
        
        return True
        
    except:
        return False

def get_ip_address(packet: bytes) -> Tuple[str, str]:
    """Extract source and destination IP from packet"""
    if len(packet) < 20:
        return "", ""
    
    src_ip = '.'.join(str(b) for b in packet[12:16])
    dst_ip = '.'.join(str(b) for b in packet[16:20])
    
    return src_ip, dst_ip

def calculate_checksum(data: bytes) -> int:
    """Calculate IP checksum"""
    if len(data) % 2 == 1:
        data += b'\x00'
    
    s = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) + data[i+1]
        s = (s + w) & 0xFFFF
    
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    
    return ~s & 0xFFFF

def is_private_ip(ip: str) -> bool:
    """Check if IP is in private range"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except:
        return False

def get_external_interface() -> str:
    """Get external network interface"""
    try:
        # Read routing table
        with open('/proc/net/route', 'r') as f:
            for line in f.readlines()[1:]:  # Skip header
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == '00000000':  # Default route
                    return parts[0]
    except:
        pass
    
    # Fallback to common interface names
    for iface in ['eth0', 'ens3', 'venet0', 'enp0s3']:
        if os.path.exists(f'/sys/class/net/{iface}'):
            return iface
    
    return 'eth0'
