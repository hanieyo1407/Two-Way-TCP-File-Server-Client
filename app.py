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


            try:
                filename_len_bytes = conn.recv(4)
                if not filename_len_bytes:
                    print("Client disconnected before sending filename length.")

                filename_len_bytes = struct.unpack('!I', filename_len_bytes)[0]

                filename = conn.recv(filename_len_bytes).decode('utf-8')
                save_path = os.path.join(save_directory, filename)
                print(f"Receiving file: {filename} and saving to {save_path}")


                file_size_bytes = conn.recv(8)
                if not file_size_bytes:
                    print("Client disconnected before sending file size.")
                    return
                file_size = struct.unpack('!Q', file_size_bytes)[0]
                print(f"Expected file size : {file_size} bytes.")

                received_bytes = 0
                with open(save_path, 'wb') as f:
                    while received_bytes < file_size:
                        bytes_to_read = min(BUFFER_SIZE, file_size - received_bytes)
                        data = conn.recv(bytes_to_read)
                        if not data:
                            print("Client disconnected prematurely.")
                            break
                        f.write(data)
                        received_bytes += len(data)
                        print(f"Recceived {received_bytes}/{file_size} bytes ({((received_bytes/file_size)*100):.2f}%)",end='\r')
                print(f"\n successfully received '{filename}'. Total bytes: {received_bytes}")

            except ConnectionResetError:
                print("Client unexpectedly disconnected🥺!")
            except Exception as e:
                print(f"An Error occured during file reception: {e}")
            finally:
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
