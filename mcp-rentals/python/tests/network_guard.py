"""Pytest plugin that disables network access during offline provider tests."""

import socket


def deny_network_access(*_arguments, **_keywords):
    """Reject socket operations that could reach a remote host."""
    raise RuntimeError("Network access is disabled for provider offline tests")


def pytest_configure(config):
    """Install socket guards after pytest and test dependencies are loaded."""
    socket.socket.connect = deny_network_access
    socket.socket.connect_ex = deny_network_access
    socket.socket.sendto = deny_network_access
    socket.create_connection = deny_network_access
    socket.getaddrinfo = deny_network_access
