import struct

MAGIC = b'\xAA\x55'
CMD_DATA = 1
CMD_KEEP = 2
CMD_FAKE = 3

def pack(sid, seq, payload):
    header = struct.pack("!2sIIH", MAGIC, sid, seq, len(payload))
    return header + payload

def unpack(data):
    if len(data) < 12:
        return None
    magic, sid, seq, ln = struct.unpack("!2sIIH", data[:12])
    if magic != MAGIC or len(data) < 12 + ln:
        return None
    return sid, seq, data[12:12+ln]
