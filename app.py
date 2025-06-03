import socket
import os
import struct

HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 4096
def start_server_receive_file(host, port, save_directory = "received_files"):
    print(f"Sever144 starting on {host}:{port}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        print("Socket bound!")

        s.listen()
        print("Server listening for connections...")

        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")

            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
                print(f"Created directory: {save_directory}")
            print("Connection closed")



def start_client_send_file(host, port, file_path_to_send = "tst_file.txt"):
    print(f"Client attempting to connect to {host}:{port}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print(f"connected to server at {host}:{port}")

        print(f"Ready to send file: {file_path_to_send}")
        print("Connection closed.")


if __name__ == "__main__":
    if not os.path.exists("received_files"):
        os.makedirs("received_files")
    start_server_receive_file(HOST, PORT)
