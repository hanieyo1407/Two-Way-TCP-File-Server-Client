import socket
import os
import struct
import argparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 65432
BUFFER_SIZE = 4096
SERVER_UPLOADS = "server_uploads"
CLIENT_DOWNLOADS = "client_downloads"


def receive_exactly(sock, num_bytes):
    data = b''
    while len(data) < num_bytes:
        chunk = sock.recv(num_bytes - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def handle_upload(conn, addr):
    print(f"-> Received UPLD command from {addr}")
    try:
        filename_len_bytes = receive_exactly(conn, 4)
        if not filename_len_bytes: return
        filename_len = struct.unpack('!I', filename_len_bytes)[0]

        filename_bytes = receive_exactly(conn, filename_len)
        if not filename_bytes: return
        filename = filename_bytes.decode('utf-8')

        save_path = os.path.join(SERVER_UPLOADS, os.path.basename(filename))

        file_size_bytes = receive_exactly(conn, 8)
        if not file_size_bytes: return
        file_size = struct.unpack('!Q', file_size_bytes)[0]

        print(f"Receiving file: {filename} ({file_size} bytes)")

        received_bytes = 0
        with open(save_path, 'wb') as f:
            while received_bytes < file_size:
                bytes_to_read = min(BUFFER_SIZE, file_size - received_bytes)
                data = receive_exactly(conn, bytes_to_read)
                if not data:
                    print("Client disconnected prematurely.")
                    break
                f.write(data)
                received_bytes += len(data)

        print(f"Successfully received and saved '{filename}'")
        conn.sendall(b"OK")

    except Exception as e:
        print(f"Error during upload from {addr}: {e}")
        conn.sendall(b"ERROR")


def handle_download(conn, addr):
    print(f"-> Received DNLD command from {addr}")
    try:
        filename_len_bytes = receive_exactly(conn, 4)
        if not filename_len_bytes: return
        filename_len = struct.unpack('!I', filename_len_bytes)[0]

        filename_bytes = receive_exactly(conn, filename_len)
        if not filename_bytes: return
        filename = filename_bytes.decode('utf-8')

        print(f"Client {addr} requests to download '{filename}'")

        filepath = os.path.join(SERVER_UPLOADS, os.path.basename(filename))

        if not os.path.exists(filepath):
            print(f"File '{filename}' not found for download.")
            conn.sendall(struct.pack('!Q', 0))  # Send size 0 to indicate error
            return

        file_size = os.path.getsize(filepath)
        conn.sendall(struct.pack('!Q', file_size))

        with open(filepath, 'rb') as f:
            sent_bytes = 0
            while sent_bytes < file_size:
                chunk = f.read(BUFFER_SIZE)
                if not chunk: break
                conn.sendall(chunk)
                sent_bytes += len(chunk)
        print(f"Successfully sent '{filename}' to {addr}")

    except Exception as e:
        print(f"Error during download for {addr}: {e}")


def handle_client_connection(conn, addr):
    print(f"Handling connection from {addr}")
    try:
        command_bytes = receive_exactly(conn, 4)
        if not command_bytes:
            print(f"Client {addr} disconnected before sending command.")
            return

        command = command_bytes.decode('utf-8').strip()
        if command == 'UPLD':
            handle_upload(conn, addr)
        elif command == 'DNLD':
            handle_download(conn, addr)
        else:
            print(f"Unknown command '{command}' from {addr}")
    except Exception as e:
        print(f"An error occurred with client {addr}: {e}")
    finally:
        print(f"Closing connection with {addr}")
        conn.close()


def start_server(host, port):
    os.makedirs(SERVER_UPLOADS, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"Server started on {host}:{port}, listening for clients...")
        while True:
            try:
                conn, addr = s.accept()
                handle_client_connection(conn, addr)
            except KeyboardInterrupt:
                print("\nServer shutting down.")
                break
            except Exception as e:
                print(f"Server main loop error: {e}")


def client_upload_file(host, port, file_path):
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            s.sendall(b'UPLD')

            filename = os.path.basename(file_path)
            filename_bytes = filename.encode('utf-8')
            s.sendall(struct.pack('!I', len(filename_bytes)))
            s.sendall(filename_bytes)

            file_size = os.path.getsize(file_path)
            s.sendall(struct.pack('!Q', file_size))

            with open(file_path, 'rb') as f:
                sent_bytes = 0
                while sent_bytes < file_size:
                    data = f.read(BUFFER_SIZE)
                    if not data: break
                    s.sendall(data)
                    sent_bytes += len(data)

            print(f"File '{filename}' sent. Waiting for server confirmation...")
            response = s.recv(1024)
            print(f"Server response: {response.decode('utf-8')}")
        except Exception as e:
            print(f"An error occurred during upload: {e}")


def client_download_file(host, port, filename):
    os.makedirs(CLIENT_DOWNLOADS, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            s.sendall(b'DNLD')

            filename_bytes = filename.encode('utf-8')
            s.sendall(struct.pack('!I', len(filename_bytes)))
            s.sendall(filename_bytes)

            file_size_bytes = receive_exactly(s, 8)
            if not file_size_bytes:
                print("Server disconnected.")
                return

            file_size = struct.unpack('!Q', file_size_bytes)[0]
            if file_size == 0:
                print(f"Server indicated file '{filename}' not found.")
                return

            print(f"Downloading '{filename}' ({file_size} bytes)...")
            save_path = os.path.join(CLIENT_DOWNLOADS, os.path.basename(filename))
            received_bytes = 0
            with open(save_path, 'wb') as f:
                while received_bytes < file_size:
                    bytes_to_read = min(BUFFER_SIZE, file_size - received_bytes)
                    data = receive_exactly(s, bytes_to_read)
                    if not data:
                        print("Server disconnected prematurely.")
                        break
                    f.write(data)
                    received_bytes += len(data)
            print(f"Successfully downloaded and saved '{filename}'")
        except Exception as e:
            print(f"An error occurred during download: {e}")


def main():
    parser = argparse.ArgumentParser(description="TCP Two-Way File Transfer Tool")
    subparsers = parser.add_subparsers(dest='mode', required=True)

    server_parser = subparsers.add_parser('server', help='Run in server mode')
    server_parser.add_argument('--host', default=DEFAULT_HOST)
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT)

    client_parser = subparsers.add_parser('client', help='Run in client mode')
    client_subparsers = client_parser.add_subparsers(dest='action', required=True)

    upload_parser = client_subparsers.add_parser('upload', help='Upload a file to the server')
    upload_parser.add_argument('--file', required=True, help='Path of the file to upload')
    upload_parser.add_argument('--host', default=DEFAULT_HOST)
    upload_parser.add_argument('--port', type=int, default=DEFAULT_PORT)

    download_parser = client_subparsers.add_parser('download', help='Download a file from the server')
    download_parser.add_argument('--file', required=True, help='Name of the file to download')
    download_parser.add_argument('--host', default=DEFAULT_HOST)
    download_parser.add_argument('--port', type=int, default=DEFAULT_PORT)

    args = parser.parse_args()

    if args.mode == 'server':
        start_server(args.host, args.port)
    elif args.mode == 'client':
        if args.action == 'upload':
            client_upload_file(args.host, args.port, args.file)
        elif args.action == 'download':
            client_download_file(args.host, args.port, args.file)


if __name__ == "__main__":
    main()