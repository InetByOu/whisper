#!/usr/bin/env python3
import socket
import struct
import select
import time
import threading
from collections import deque
import os

class OptimizedUDPServer:
    def __init__(self, host='0.0.0.0', port=5555, mtu=1350):
        self.host = host
        self.port = port
        self.mtu = mtu
        
        # Client session tracking
        self.clients = {}  # (ip, port) -> {'last_seen': time, 'seq': seq}
        self.session_timeout = 30  # seconds
        
        # Packet buffers per client
        self.client_buffers = {}
        
        # Statistics
        self.stats = {
            'packets_received': 0,
            'packets_forwarded': 0,
            'packets_dropped': 0,
            'bytes_received': 0,
            'clients_connected': 0
        }
        
        # Optimize socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set socket buffer sizes (BEFORE bind)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024)  # 10MB
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 10 * 1024 * 1024)  # 10MB
        
        # Reuse address
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Enable UDP checksum (important!)
        if hasattr(socket, 'SO_NO_CHECK'):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_NO_CHECK, 0)
        
        self.sock.bind((self.host, self.port))
        
        # Non-blocking
        self.sock.setblocking(False)
        
        print(f"[+] UDP Tunnel Server started on {host}:{port}")
        print(f"[+] MTU: {mtu}, Buffer: 10MB")
        
    def start(self):
        """Start main server loop with select for efficiency"""
        inputs = [self.sock]
        
        while True:
            try:
                # Use select for efficient I/O multiplexing
                readable, _, _ = select.select(inputs, [], [], 1.0)
                
                for sock in readable:
                    if sock is self.sock:
                        self.handle_incoming()
                
                # Cleanup old sessions every 10 seconds
                if int(time.time()) % 10 == 0:
                    self.cleanup_sessions()
                    
            except KeyboardInterrupt:
                print("\n[!] Shutting down server...")
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                continue
    
    def handle_incoming(self):
        """Handle incoming UDP packets with minimal processing"""
        try:
            data, addr = self.sock.recvfrom(self.mtu + 100)  # Allow some overhead
            
            self.stats['packets_received'] += 1
            self.stats['bytes_received'] += len(data)
            
            # Update client session
            self.clients[addr] = {
                'last_seen': time.time(),
                'seq': self.stats['packets_received'] % 65536
            }
            
            # Simple protocol: first byte = packet type
            if len(data) < 1:
                self.stats['packets_dropped'] += 1
                return
                
            packet_type = data[0]
            
            if packet_type == 0x01:  # Data packet
                # Extract sequence number (bytes 1-2)
                if len(data) >= 3:
                    seq = struct.unpack('>H', data[1:3])[0]
                    
                    # Simple out-of-order detection (allow some reordering)
                    if addr in self.clients:
                        expected_seq = (self.clients[addr]['seq'] + 1) % 65536
                        diff = (seq - expected_seq) % 65536
                        
                        if diff > 1000:  # Too far out-of-order
                            self.stats['packets_dropped'] += 1
                            return
                    
                    # Forward packet to client (simplified - in reality would forward to TUN)
                    self.forward_packet(data[3:], addr)
                    
            elif packet_type == 0x02:  # Keepalive packet
                # Just update timestamp, no forwarding needed
                self.send_keepalive_ack(addr)
                
        except socket.error as e:
            if e.errno != socket.EAGAIN:
                print(f"[!] Socket error: {e}")
    
    def forward_packet(self, data, client_addr):
        """Forward packet with minimal processing"""
        try:
            # In real implementation, this would send to TUN interface
            # For demo, just echo back
            response = bytes([0x01]) + struct.pack('>H', self.stats['packets_forwarded'] % 65536) + data
            
            if len(response) > self.mtu:
                # Fragment or drop (better to fragment at IP level)
                print(f"[!] Packet too large: {len(response)} > {self.mtu}")
                return
                
            self.sock.sendto(response, client_addr)
            self.stats['packets_forwarded'] += 1
            
        except Exception as e:
            print(f"[!] Forward error: {e}")
            self.stats['packets_dropped'] += 1
    
    def send_keepalive_ack(self, addr):
        """Send keepalive acknowledgement"""
        ack = bytes([0x02]) + struct.pack('>Q', int(time.time() * 1000))
        try:
            self.sock.sendto(ack, addr)
        except:
            pass
    
    def cleanup_sessions(self):
        """Remove inactive client sessions"""
        current_time = time.time()
        to_remove = []
        
        for addr, info in self.clients.items():
            if current_time - info['last_seen'] > self.session_timeout:
                to_remove.append(addr)
        
        for addr in to_remove:
            del self.clients[addr]
            if addr in self.client_buffers:
                del self.client_buffers[addr]
        
        if to_remove:
            print(f"[+] Cleaned up {len(to_remove)} inactive sessions")
    
    def print_stats(self):
        """Print server statistics"""
        print(f"\n{'='*50}")
        print(f"Server Statistics:")
        print(f"  Packets Received:  {self.stats['packets_received']}")
        print(f"  Packets Forwarded: {self.stats['packets_forwarded']}")
        print(f"  Packets Dropped:   {self.stats['packets_dropped']}")
        print(f"  Bytes Received:    {self.stats['bytes_received']:,}")
        print(f"  Active Clients:    {len(self.clients)}")
        print(f"{'='*50}")

if __name__ == "__main__":
    # Set MTU untuk menghindari fragmentation
    # Alasan MTU 1350: 
    # - Ethernet MTU 1500 dikurangi overhead UDP/IP (28 byte) = 1472
    # - Tapi jaringan mobile sering punya MTU lebih kecil (~1400)
    # - Buffer 50 byte untuk header tunnel dan variasi network
    server = OptimizedUDPServer(port=5555, mtu=1350)
    
    # Start stats thread
    stats_thread = threading.Thread(target=lambda: [
        time.sleep(10),
        server.print_stats()
    ] * 100, daemon=True)
    stats_thread.start()
    
    server.start()
