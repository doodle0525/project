import socket
import threading
import sys
from common import (
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_GROUP,
    MSG_PRIVATE,
    MSG_TYPING,
    MSG_DELIVERED,
    MSG_SEEN,
    MSG_USERS,
    MSG_USERS_RESP,
    MSG_NOTIFICATION,
    MSG_ERROR,
    MSG_JOIN_ROOM,
    MSG_ROOMS,
    MSG_ROOMS_RESP,
    send_msg,
    recv_msg
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080

clients = {}
clients_lock = threading.Lock()

rooms = {
    "general": set(),
    "friends": set(),
    "project": set()
}
client_rooms = {}


def broadcast_room(room_name, msg_dict, exclude_username=None):
    with clients_lock:
        member_names = list(rooms.get(room_name, set()))
        targets = [(u, clients[u]) for u in member_names if u in clients]

    for username, sock in targets:
        if username != exclude_username:
            send_msg(sock, msg_dict)


def broadcast(msg_dict, exclude_username=None):

    with clients_lock:
        targets = list(clients.items())

    for username, sock in targets:
        if username != exclude_username:
            send_msg(sock, msg_dict)


def send_to_user(target_username, msg_dict):

    with clients_lock:
        target_sock = clients.get(target_username)

    if target_sock:
        return send_msg(target_sock, msg_dict)
    return False


def handle_client(conn, addr):

    username = None
    try:
        # Step 1: Handshake & Registration
        reg_msg = recv_msg(conn)
        if not reg_msg or reg_msg.get("type") != MSG_REGISTER:
            conn.close()
            return

        requested_name = str(reg_msg.get("username", "")).strip()

        with clients_lock:
            if not requested_name or requested_name in clients or requested_name.upper() == "SERVER":
                # Username is taken or invalid
                send_msg(conn, {
                    "type": MSG_REGISTER_ACK,
                    "success": False,
                    "message": f"Username '{requested_name}' is already taken or invalid."
                })
                conn.close()
                return

            username = requested_name
            clients[username] = conn
            client_rooms[username] = "general"
            rooms["general"].add(username)

        send_msg(conn, {
            "type": MSG_REGISTER_ACK,
            "success": True,
            "message": "Welcome to SecureChat! You are in room 'general'."
        })

        print(f"[+] Client connected: {username} from {addr[0]}:{addr[1]} in room 'general'")

        broadcast_room("general", {
            "type": MSG_NOTIFICATION,
            "content": f"{username} joined the chat in room 'general'."
        }, exclude_username=username)

        while True:
            msg = recv_msg(conn)
            if msg is None:
                break

            m_type = msg.get("type")

            if m_type == MSG_GROUP:
                current_room = client_rooms.get(username, "general")
                broadcast_room(current_room, {
                    "type": MSG_GROUP,
                    "room": current_room,
                    "sender": username,
                    "content": content
                }, exclude_username=username)

            elif m_type == MSG_JOIN_ROOM:
                new_room = str(msg.get("room", "general")).strip().lower()
                if not new_room:
                    new_room = "general"
                old_room = client_rooms.get(username, "general")

                if new_room == old_room:
                    send_msg(conn, {
                        "type": MSG_NOTIFICATION,
                        "content": f"You are already in room '{new_room}'."
                    })
                else:
                    with clients_lock:
                        if old_room in rooms and username in rooms[old_room]:
                            rooms[old_room].remove(username)
                        
                        rooms.setdefault(new_room, set()).add(username)
                        client_rooms[username] = new_room

                    
                    broadcast_room(old_room, {
                        "type": MSG_NOTIFICATION,
                        "content": f"{username} left room '{old_room}'."
                    })

                    broadcast_room(new_room, {
                        "type": MSG_NOTIFICATION,
                        "content": f"{username} joined room '{new_room}'."
                    }, exclude_username=username)

                    send_msg(conn, {
                        "type": MSG_NOTIFICATION,
                        "content": f"Switched to room '{new_room}'."
                    })

            elif m_type == MSG_ROOMS:

                with clients_lock:
                    room_summary = {r: len(u_set) for r, u_set in rooms.items()}
                    current_room = client_rooms.get(username, "general")
                send_msg(conn, {
                    "type": MSG_ROOMS_RESP,
                    "rooms": room_summary,
                    "current": current_room
                })

            elif m_type == MSG_PRIVATE:
                target = msg.get("target")
                content = msg.get("content", "")
                msg_id = msg.get("msg_id", "")

                delivered = send_to_user(target, {
                    "type": MSG_PRIVATE,
                    "sender": username,
                    "content": content,
                    "msg_id": msg_id
                })

                if not delivered:

                    send_msg(conn, {
                        "type": MSG_ERROR,
                        "message": f"User '{target}' is offline or does not exist."
                    })

            elif m_type == MSG_TYPING:
                # Forward typing indicator to intended recipient
                target = msg.get("target")
                send_to_user(target, {
                    "type": MSG_TYPING,
                    "sender": username
                })

            elif m_type == MSG_DELIVERED:
            
                target = msg.get("target")
                msg_id = msg.get("msg_id")
                send_to_user(target, {
                    "type": MSG_DELIVERED,
                    "target": username,
                    "msg_id": msg_id
                })

            elif m_type == MSG_SEEN:
                target = msg.get("target")
                msg_id = msg.get("msg_id")
                send_to_user(target, {
                    "type": MSG_SEEN,
                    "target": username,
                    "msg_id": msg_id
                })

            elif m_type == MSG_USERS:
            
                with clients_lock:
                    online_list = sorted(list(clients.keys()))
                send_msg(conn, {
                    "type": MSG_USERS_RESP,
                    "users": online_list
                })

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        # Cleanup on client disconnect
        if username:
            with clients_lock:
                if username in clients:
                    del clients[username]
                curr_room = client_rooms.pop(username, "general")
                if curr_room in rooms and username in rooms[curr_room]:
                    rooms[curr_room].remove(username)
            print(f"[-] Client disconnected: {username}")
            broadcast_room(curr_room, {
                "type": MSG_NOTIFICATION,
                "content": f"{username} left the chat."
            })
        try:
            conn.close()
        except OSError:
            pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    host = DEFAULT_HOST

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_sock.bind((host, port))

    server_sock.listen(10)

    print("=" * 50)
    print("   SECURE CHAT SERVER (TCP MULTI-CLIENT)")
    print(f"   Listening on: {host}:{port}")
    print("   Default Port: 8080")
    print("   Press Ctrl+C to stop the server.")
    print("=" * 50)

    try:
        while True:
            conn, addr = server_sock.accept()

            client_thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            )
            client_thread.start()

    except KeyboardInterrupt:
        print("\n[!] Server shutting down...")
    finally:
        with clients_lock:
            for sock in clients.values():
                try:
                    sock.close()
                except OSError:
                    pass
            clients.clear()
            client_rooms.clear()
            for r in rooms:
                rooms[r].clear()
        server_sock.close()
        print("[*] Server closed successfully.")


if __name__ == "__main__":
    main()
