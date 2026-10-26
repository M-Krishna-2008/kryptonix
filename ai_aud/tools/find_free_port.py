"""Helper script to find the first available local port starting at 8000."""
import socket
import sys

def find_port(start_port: int = 8000) -> int:
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(find_port(start))
