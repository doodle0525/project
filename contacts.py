"""
contacts.py - Simple Text-File Contact Management for SecureChat

Stores server contact names and IP addresses in contacts.txt so users
can easily connect without memorizing IP addresses.
"""

import os

CONTACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts.txt")


def load_contacts(filepath=CONTACTS_FILE):
    """
    Loads saved contacts from contacts.txt.
    Returns a dictionary of {name: ip}.
    """
    contacts = {}
    if not os.path.exists(filepath):
        return contacts

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "," in line:
                name, ip = line.split(",", 1)
                contacts[name.strip()] = ip.strip()
    return contacts


def save_contacts(contacts, filepath=CONTACTS_FILE):
    """
    Writes the contacts dictionary back to contacts.txt.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        for name, ip in contacts.items():
            f.write(f"{name},{ip}\n")


def add_contact(name, ip, filepath=CONTACTS_FILE):
    """Adds a new contact to contacts.txt."""
    name = name.strip()
    ip = ip.strip()
    contacts = load_contacts(filepath)
    if name in contacts:
        return False, f"Contact '{name}' already exists. Use update instead."
    contacts[name] = ip
    save_contacts(contacts, filepath)
    return True, f"Contact '{name}' ({ip}) added successfully."


def delete_contact(name, filepath=CONTACTS_FILE):
    """Deletes an existing contact from contacts.txt."""
    name = name.strip()
    contacts = load_contacts(filepath)
    if name not in contacts:
        return False, f"Contact '{name}' does not exist."
    del contacts[name]
    save_contacts(contacts, filepath)
    return True, f"Contact '{name}' deleted successfully."


def update_contact(name, ip, filepath=CONTACTS_FILE):
    """Updates an existing contact's IP address."""
    name = name.strip()
    ip = ip.strip()
    contacts = load_contacts(filepath)
    if name not in contacts:
        return False, f"Contact '{name}' not found. Use add to create it."
    contacts[name] = ip
    save_contacts(contacts, filepath)
    return True, f"Contact '{name}' updated to {ip}."


def list_contacts(filepath=CONTACTS_FILE):
    """Returns a list of tuples [(name, ip), ...]."""
    contacts = load_contacts(filepath)
    return sorted(contacts.items())
