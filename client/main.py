#!/usr/bin/env python3
"""
UDTUN Client Main Entry Point
"""

import sys
import time
import threading
import logging

from .config import config, load_config
from .tun import TUNClient
from .udp import UDPClient

class UDTUNClient:
    """Main UDTUN client class"""
    
    def __init__(self):
        self.tun = TUNClient()
        self.udp = UDPClient()
        self.running = False
        self.stats = {
            'tun_to_udp': 0,
            'udp_to_tun': 0,
            'errors': 0
        }
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(config.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("udtun-client")
    
    def start(self):
        """Start the client"""
        self.logger.info("Starting UDTUN Client...")
        self.logger.info(f"Server: {config.server_ip}")
        self.logger.info(f"TUN IP: {config.tun_ip}")
        
        # Setup packet handlers
        self.tun.set_packet_handler(self._handle_tun_packet)
        self.udp.receive_handler = self._handle_udp_packet
        
        # Start components
        try:
            self.tun.start()
            self.udp.start()
        except Exception as e:
            self.logger.error(f"Failed to start client: {e}")
            self.cleanup()
            sys.exit(1)
        
        self.running = True
        self.logger.info("Client started successfully")
        
        # Start UDP receive thread
        udp_thread = threading.Thread(target=self.udp.receive_loop, daemon=True)
        udp_thread.start()
        
        # Main loop
        self._main_loop()
    
    def _main_loop(self):
        """Main client loop"""
        last_stats_time = time.time()
        
        while self.running:
            try:
                # Check connection
                if not self.udp.connected:
                    self.logger.warning("Not connected, attempting to reconnect...")
                    self.udp.reconnect()
                
                # Log statistics
                now = time.time()
                if now - last_stats_time > 10:
                    self._log_stats()
                    last_stats_time = now
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                self.logger.info("Shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.stats['errors'] += 1
                time.sleep(1)
    
    def _handle_tun_packet(self, ip_packet: bytes):
        """Handle packet from TUN (send to server)"""
        if not self.udp.connected:
            return
        
        encoded = self.udp.encode_packet(ip_packet)
        self.udp.send_packet(encoded)
        self.stats['tun_to_udp'] += 1
    
    def _handle_udp_packet(self, udp_packet: bytes):
        """Handle packet from UDP (send to TUN)"""
        ip_packet = self.udp.decode_packet(udp_packet)
        if ip_packet:
            self.tun.write_packet(ip_packet)
            self.stats['udp_to_tun'] += 1
    
    def _log_stats(self):
        """Log client statistics"""
        self.logger.info(
            f"Stats: TUN→UDP={self.stats['tun_to_udp']} | "
            f"UDP→TUN={self.stats['udp_to_tun']} | "
            f"Errors={self.stats['errors']} | "
            f"Connected={self.udp.connected}"
        )
    
    def cleanup(self):
        """Cleanup resources"""
        self.running = False
        self.udp.stop()
        self.tun.stop()
        self.logger.info("Client shutdown complete")

def main():
    """Main entry point"""
    # Load configuration
    if len(sys.argv) > 1:
        load_config(sys.argv[1])
    else:
        # Try default config file
        load_config("/etc/udtun/client.json")
    
    # Create and start client
    client = UDTUNClient()
    client.start()

if __name__ == "__main__":
    main()
