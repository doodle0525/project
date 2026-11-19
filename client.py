
import socket
import threading
import sys
import os
import time
import uuid

import common
import contacts

DEFAULT_PORT = 8080
last_typing_time = {}  


def print_help():
    print("""
Available Commands:
  /help                   Show this help message
  /rooms                  List available chat rooms
  /join ROOM              Join or create a room (e.g. /join friends)
  /users                  List all online users
  /pm USER MESSAGE        Send a private message to USER
  /typing USER            Send a typing indicator to USER
  /contacts               Show saved server contacts
  /contact add NAME IP    Save a new contact
  /contact delete NAME    Delete a saved contact
  /contact update NAME IP Update an existing contact
  /quit                   Disconnect and exit
  <message>               Normal text is sent to everyone in your current room
""")


def receive_thread(sock, running_flag, my_username):
    while running_flag[0]:
        msg = common.recv_msg(sock)
        if msg is None:
            if running_flag[0]:
                print("\n[SERVER] Disconnected from chat server.")
                running_flag[0] = False
            break

        m_type = msg.get("type")

        if m_type == common.MSG_NOTIFICATION:
            print(f"\n[SERVER] {msg.get('content')}")

        elif m_type == common.MSG_GROUP:
            room = msg.get("room", "general")
            sender = msg.get("sender")
            content = msg.get("content")
            print(f"\n[{room}] [{sender}]: {content}")

        elif m_type == common.MSG_ROOMS_RESP:
            room_data = msg.get("rooms", {})
            cur = msg.get("current", "general")
            print("\n--- Available Chat Rooms ---")
            for r_name, count in room_data.items():
                marker = " *(active)*" if r_name == cur else ""
                print(f"  • {r_name} ({count} user{'s' if count != 1 else ''}){marker}")
            print("----------------------------")
            print("Tip: Use /join <room_name> to switch or create a room.")

        elif m_type == common.MSG_PRIVATE:
            sender = msg.get("sender")
            content = msg.get("content")
            msg_id = msg.get("msg_id")

            
            print(f"\n[Private from {sender}]: {content}")

            
            common.send_msg(sock, {
                "type": common.MSG_DELIVERED,
                "target": sender,
                "msg_id": msg_id
            })

            # Send SEEN 
            common.send_msg(sock, {
                "type": common.MSG_SEEN,
                "target": sender,
                "msg_id": msg_id
            })

        elif m_type == common.MSG_DELIVERED:
            target = msg.get("target")
            print(f"\n[STATUS] Message delivered to {target}")

        elif m_type == common.MSG_SEEN:
            target = msg.get("target")
            print(f"\n[STATUS] {target} has seen your message")

        elif m_type == common.MSG_TYPING:
            sender = msg.get("sender")
            print(f"\n[{sender} is typing...]")

        elif m_type == common.MSG_USERS_RESP:
            user_list = msg.get("users", [])
            print(f"\n[ONLINE USERS]: {', '.join(user_list)}")

        elif m_type == common.MSG_ERROR:
            print(f"\n[ERROR] {msg.get('message')}")


def select_server_ip():
    saved = contacts.load_contacts()
    contact_items = list(saved.items())

    if contact_items:
        print("\nSaved Server Contacts:")
        for idx, (name, ip) in enumerate(contact_items, 1):
            print(f"  [{idx}] {name} ({ip})")
        print()

    choice = input("Enter server IP or contact number/name [127.0.0.1]: ").strip()

   
    if not choice:
        return "127.0.0.1"

    
    if choice.isdigit():
        num = int(choice)
        if 1 <= num <= len(contact_items):
            selected_name, selected_ip = contact_items[num - 1]
            print(f"[*] Selected contact [{num}] {selected_name} -> {selected_ip}")
            return selected_ip

    
    for name, ip in contact_items:
        if name.lower() == choice.lower():
            print(f"[*] Selected contact '{name}' -> {ip}")
            return ip

    
    return choice


def main():
    print("=" * 36)
    print("========== SECURE CHAT ==========")
    print("=" * 36)

    
    username = input("Enter username: ").strip()
    while not username or " " in username:
        print("Username cannot be empty or contain spaces.")
        username = input("Enter username: ").strip()

    
    server_ip = select_server_ip()
    port = DEFAULT_PORT

    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((server_ip, port))
    except Exception as e:
        print(f"\n[!] Could not connect to server at {server_ip}:{port} ({e})")
        sys.exit(1)

    
    common.send_msg(sock, {
        "type": common.MSG_REGISTER,
        "username": username
    })

    ack = common.recv_msg(sock)
    if not ack or not ack.get("success"):
        error_msg = ack.get("message") if ack else "Connection closed by server."
        print(f"\n[!] Registration failed: {error_msg}")
        sock.close()
        sys.exit(1)

    print("\nConnected successfully!")
    print("Type /help to see all available commands.\n")

    
    running_flag = [True]
    recv_t = threading.Thread(
        target=receive_thread,
        args=(sock, running_flag, username),
        daemon=True
    )
    recv_t.start()

    try:
        while running_flag[0]:
            try:
                user_input = input().strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input == "/help":
                print_help()

            
            elif user_input == "/quit":
                print("\nDisconnecting...")
                running_flag[0] = False
                break

           
            elif user_input == "/rooms":
                common.send_msg(sock, {"type": common.MSG_ROOMS})

            
            elif user_input.startswith("/join "):
                parts = user_input.split(" ", 1)
                if len(parts) < 2 or not parts[1].strip():
                    print("Usage: /join <room_name>")
                else:
                    room_name = parts[1].strip()
                    common.send_msg(sock, {
                        "type": common.MSG_JOIN_ROOM,
                        "room": room_name
                    })

            
            elif user_input == "/users":
                common.send_msg(sock, {"type": common.MSG_USERS})

            
            elif user_input.startswith("/pm "):
                parts = user_input.split(" ", 2)
                if len(parts) < 3:
                    print("Usage: /pm <username> <message>")
                    continue
                target_user = parts[1]
                pm_text = parts[2]
                msg_id = str(uuid.uuid4())[:8]

                sent = common.send_msg(sock, {
                    "type": common.MSG_PRIVATE,
                    "target": target_user,
                    "content": pm_text,
                    "msg_id": msg_id
                })
                if sent:
                    print(f"[{username} -> {target_user}] Private: {pm_text}")
                    print("[STATUS] Message sent")

            
            elif user_input.startswith("/typing "):
                parts = user_input.split(" ", 1)
                if len(parts) < 2:
                    print("Usage: /typing <username>")
                    continue
                target_user = parts[1]

                
                now = time.time()
                if target_user in last_typing_time and (now - last_typing_time[target_user]) < 2.0:
                    print(f"[!] Please wait a moment before sending another typing indicator to {target_user}.")
                    continue

                last_typing_time[target_user] = now
                common.send_msg(sock, {
                    "type": common.MSG_TYPING,
                    "target": target_user
                })
                print(f"[Typing notification sent to {target_user}]")

            
            elif user_input == "/contacts":
                saved = contacts.list_contacts()
                if not saved:
                    print("[CONTACTS] No saved contacts found.")
                else:
                    print("\n--- Saved Contacts ---")
                    for name, ip in saved:
                        print(f"  - {name}: {ip}")
                    print("----------------------")

            
            elif user_input.startswith("/contact add "):
                parts = user_input.split()
                if len(parts) != 4:
                    print("Usage: /contact add <name> <ip>")
                else:
                    ok, msg_text = contacts.add_contact(parts[2], parts[3])
                    print(f"[CONTACTS] {msg_text}")

            
            elif user_input.startswith("/contact delete "):
                parts = user_input.split()
                if len(parts) != 3:
                    print("Usage: /contact delete <name>")
                else:
                    ok, msg_text = contacts.delete_contact(parts[2])
                    print(f"[CONTACTS] {msg_text}")

            
            elif user_input.startswith("/contact update "):
                parts = user_input.split()
                if len(parts) != 4:
                    print("Usage: /contact update <name> <ip>")
                else:
                    ok, msg_text = contacts.update_contact(parts[2], parts[3])
                    print(f"[CONTACTS] {msg_text}")

            
            elif user_input.startswith("/"):
                print(f"Unknown command '{user_input}'. Type /help for command list.")

            
            else:
                common.send_msg(sock, {
                    "type": common.MSG_GROUP,
                    "content": user_input
                })

    except KeyboardInterrupt:
        print("\n[!] Exiting...")
    finally:
        running_flag[0] = False
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        print("Goodbye!")


if __name__ == "__main__":
    main()
