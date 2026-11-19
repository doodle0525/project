"""
common.py - Shared Protocol and Socket Utilities for SecureChat

This module defines:
1. Message type constants for the JSON application protocol.
2. 4-byte length-prefix framing functions for TCP streams.

Why Framing is Necessary in TCP:
TCP is a byte-stream protocol, not a message-based protocol. It does NOT
preserve application message boundaries. Without framing, multiple messages
might be concatenated together, or a single message might arrive in fragments.
We prefix every JSON message with a 4-byte big-endian integer indicating
the exact byte length of the payload.
"""

import json
import struct

# Application Layer Message Types
MSG_REGISTER      = "REGISTER"       # Client registration / handshake
MSG_REGISTER_ACK  = "REGISTER_ACK"   # Server acknowledgement of registration
MSG_GROUP         = "GROUP"          # Room broadcast message
MSG_PRIVATE       = "PRIVATE"        # Direct peer-to-peer message (routed via server)
MSG_TYPING        = "TYPING"         # Typing indicator notification
MSG_DELIVERED     = "DELIVERED"      # Message delivery receipt
MSG_SEEN          = "SEEN"           # Message seen/read receipt
MSG_USERS         = "USERS"          # Online users list request
MSG_USERS_RESP    = "USERS_RESP"     # Online users list response
MSG_NOTIFICATION  = "NOTIFICATION"   # Server status notification (join/leave)
MSG_ERROR         = "ERROR"          # Error message
MSG_JOIN_ROOM     = "JOIN_ROOM"      # Join or create a chat room
MSG_ROOMS         = "ROOMS"          # List available chat rooms
MSG_ROOMS_RESP    = "ROOMS_RESP"     # Response with list of rooms


def recv_exact(sock, num_bytes):
    """
    Helper function to reliably receive exactly `num_bytes` from a TCP socket.
    Handles partial TCP receives by looping until all requested bytes are read.
    Returns bytes or None if the socket is closed.
    """
    buffer = bytearray()
    while len(buffer) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buffer))
            if not chunk:
                # Socket connection closed by remote peer
                return None
            buffer.extend(chunk)
        except (ConnectionResetError, BrokenPipeError, OSError):
            return None
    return bytes(buffer)


def send_msg(sock, data):
    """
    Serializes a Python dictionary to JSON, prefixes it with a 4-byte
    big-endian length header, and transmits it over the socket.
    """
    try:
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack(">I", len(payload))
        sock.sendall(header + payload)
        return True
    except (ConnectionResetError, BrokenPipeError, OSError):
        return False


def recv_msg(sock):
    """
    Reads a 4-byte length prefix, then reads the exact JSON payload.
    Returns the parsed Python dictionary, or None on disconnection/error.
    """
    header = recv_exact(sock, 4)
    if not header:
        return None
    (payload_len,) = struct.unpack(">I", header)
    payload_bytes = recv_exact(sock, payload_len)
    if not payload_bytes:
        return None
    try:
        return json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
