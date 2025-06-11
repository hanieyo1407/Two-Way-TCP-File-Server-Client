import wx
import socket
import threading
import os
import struct
import time


class FileTransferApp(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Two-Way TCP File Server/Client", size=(600, 500))

        self.server_socket = None
        self.server_thread = None
        self.is_server_running = False
        self.buffer_size = 4096
        self.server_uploads_dir = "server_uploads"
        self.client_downloads_dir = "client_downloads"

        os.makedirs(self.server_uploads_dir, exist_ok=True)
        os.makedirs(self.client_downloads_dir, exist_ok=True)

        self.create_gui()
        self.Center()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def create_gui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        server_box = wx.StaticBox(panel, label="Server Mode")
        server_sizer = wx.StaticBoxSizer(server_box, wx.VERTICAL)
        server_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)

        server_controls_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALL | wx.CENTER, 5)
        self.server_port = wx.TextCtrl(panel, value="65432", size=(80, -1))
        server_controls_sizer.Add(self.server_port, 0, wx.ALL, 5)
        self.server_btn = wx.Button(panel, label="Start Server")
        self.server_btn.Bind(wx.EVT_BUTTON, self.on_server_toggle)
        server_controls_sizer.Add(self.server_btn, 0, wx.ALL, 5)
        server_sizer.Add(server_controls_sizer, 0, wx.ALL, 5)
        self.server_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 150))
        server_sizer.Add(self.server_status, 1, wx.ALL | wx.EXPAND, 5)

        client_box = wx.StaticBox(panel, label="Client Mode")
        client_sizer = wx.StaticBoxSizer(client_box, wx.VERTICAL)
        connection_sizer = wx.BoxSizer(wx.HORIZONTAL)

        connection_sizer.Add(wx.StaticText(panel, label="Server IP:"), 0, wx.ALL | wx.CENTER, 5)
        self.client_ip = wx.TextCtrl(panel, value="127.0.0.1", size=(100, -1))
        connection_sizer.Add(self.client_ip, 0, wx.ALL, 5)
        connection_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALL | wx.CENTER, 5)
        self.client_port = wx.TextCtrl(panel, value="65432", size=(80, -1))
        connection_sizer.Add(self.client_port, 0, wx.ALL, 5)
        client_sizer.Add(connection_sizer, 0, wx.ALL, 5)

        transfer_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.upload_btn = wx.Button(panel, label="Upload File")
        self.upload_btn.Bind(wx.EVT_BUTTON, self.on_upload_file)
        transfer_sizer.Add(self.upload_btn, 0, wx.ALL, 5)
        self.download_btn = wx.Button(panel, label="Download File")
        self.download_btn.Bind(wx.EVT_BUTTON, self.on_download_file)
        transfer_sizer.Add(self.download_btn, 0, wx.ALL, 5)
        client_sizer.Add(transfer_sizer, 0, wx.ALL, 5)
        self.client_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 150))
        client_sizer.Add(self.client_status, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(server_sizer, 1, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(client_sizer, 1, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(main_sizer)

    def log_server(self, message):
        wx.CallAfter(self._append_to_textctrl, self.server_status, message)

    def log_client(self, message):
        wx.CallAfter(self._append_to_textctrl, self.client_status, message)

    def _append_to_textctrl(self, textctrl, message):
        textctrl.AppendText(f"[{time.strftime('%H:%M:%S')}] {message}\n")

    def on_server_toggle(self, event):
        if not self.is_server_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        try:
            port = int(self.server_port.GetValue())
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(5)
            self.is_server_running = True
            self.server_btn.SetLabel("Stop Server")
            self.server_port.Disable()
            self.log_server(f"Server started on port {port}. Listening...")
            self.server_thread = threading.Thread(target=self.server_worker, daemon=True)
            self.server_thread.start()
        except Exception as e:
            self.log_server(f"Error starting server: {str(e)}")

    def stop_server(self):
        self.is_server_running = False
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        self.server_btn.SetLabel("Start Server")
        self.server_port.Enable()
        self.log_server("Server stopped.")

    def server_worker(self):
        while self.is_server_running:
            try:
                client_socket, client_address = self.server_socket.accept()
                self.log_server(f"Accepted connection from: {client_address}")
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address),
                                                 daemon=True)
                client_thread.start()
            except (OSError, ConnectionAbortedError):
                if self.is_server_running:
                    self.log_server("Server socket was closed.")
                break
            except Exception as e:
                if self.is_server_running:
                    self.log_server(f"Server error: {str(e)}")
                break

    def handle_client(self, client_socket, client_address):
        try:
            command_data = self.receive_exactly(client_socket, 4)
            if not command_data: return
            command = command_data.decode('utf-8').strip()
            self.log_server(f"Received command: {command} from {client_address}")

            if command == "UPLD":
                self.handle_upload(client_socket, client_address)
            elif command == "DNLD":
                self.handle_download(client_socket, client_address)
            else:
                self.log_server(f"Unknown command: {command} from {client_address}")
        except Exception as e:
            self.log_server(f"Error handling client {client_address}: {str(e)}")
        finally:
            client_socket.close()
            self.log_server(f"Client {client_address} disconnected.")

    def handle_upload(self, client_socket, client_address):
        try:
            filename_length_data = self.receive_exactly(client_socket, 4)
            filename_length = struct.unpack('!I', filename_length_data)[0]
            filename_data = self.receive_exactly(client_socket, filename_length)
            filename = filename_data.decode('utf-8')
            file_size_data = self.receive_exactly(client_socket, 8)
            file_size = struct.unpack('!Q', file_size_data)[0]
            self.log_server(f"Receiving file: {filename} ({file_size} bytes)")
            filepath = os.path.join(self.server_uploads_dir, filename)
            with open(filepath, 'wb') as f:
                received_bytes = 0
                while received_bytes < file_size:
                    chunk_size = min(self.buffer_size, file_size - received_bytes)
                    chunk = self.receive_exactly(client_socket, chunk_size)
                    if not chunk: break
                    f.write(chunk)
                    received_bytes += len(chunk)
            client_socket.sendall(b"OK")
            self.log_server(f"File '{filename}' uploaded successfully.")
        except Exception as e:
            self.log_server(f"Error during upload: {str(e)}")
            try:
                client_socket.sendall(b"ERROR")
            except:
                pass

    def handle_download(self, client_socket, client_address):
        try:
            filename_length_data = self.receive_exactly(client_socket, 4)
            filename_length = struct.unpack('!I', filename_length_data)[0]
            filename_data = self.receive_exactly(client_socket, filename_length)
            filename = filename_data.decode('utf-8')
            self.log_server(f"Download request for: {filename}")
            filepath = os.path.join(self.server_uploads_dir, filename)
            if not os.path.exists(filepath):
                client_socket.sendall(struct.pack('!Q', 0))
                self.log_server(f"File not found: {filename}")
                return
            file_size = os.path.getsize(filepath)
            client_socket.sendall(struct.pack('!Q', file_size))
            with open(filepath, 'rb') as f:
                sent_bytes = 0
                while sent_bytes < file_size:
                    chunk = f.read(self.buffer_size)
                    if not chunk: break
                    client_socket.sendall(chunk)
                    sent_bytes += len(chunk)
            self.log_server(f"File '{filename}' sent successfully.")
        except Exception as e:
            self.log_server(f"Error during download: {str(e)}")

    def receive_exactly(self, sock, num_bytes):
        data = b''
        while len(data) < num_bytes:
            chunk = sock.recv(num_bytes - len(data))
            if not chunk: return None
            data += chunk
        return data

    def on_upload_file(self, event):
        with wx.FileDialog(self, "Choose file to upload", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL: return
            filepath = fileDialog.GetPath()
        upload_thread = threading.Thread(target=self.upload_file_worker, args=(filepath,), daemon=True)
        upload_thread.start()

    def upload_file_worker(self, filepath):
        try:
            server_ip = self.client_ip.GetValue()
            server_port = int(self.client_port.GetValue())
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                self.log_client(f"Connecting to {server_ip}:{server_port} for upload...")
                client_socket.connect((server_ip, server_port))
                client_socket.sendall(b"UPLD")
                filename_bytes = filename.encode('utf-8')
                client_socket.sendall(struct.pack('!I', len(filename_bytes)))
                client_socket.sendall(filename_bytes)
                client_socket.sendall(struct.pack('!Q', file_size))
                self.log_client(f"Uploading {filename} ({file_size} bytes)")
                with open(filepath, 'rb') as f:
                    sent_bytes = 0
                    while sent_bytes < file_size:
                        chunk = f.read(self.buffer_size)
                        if not chunk: break
                        client_socket.sendall(chunk)
                        sent_bytes += len(chunk)
                response = client_socket.recv(1024)
                if response == b"OK":
                    self.log_client(f"Upload successful: {filename}")
                else:
                    self.log_client(
                        f"Upload failed for {filename}. Server response: {response.decode('utf-8', errors='ignore')}")
        except Exception as e:
            self.log_client(f"Upload error: {str(e)}")

    def on_download_file(self, event):
        with wx.TextEntryDialog(self, "Enter filename to download from the server:", "Download File") as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL: return
            filename = dialog.GetValue().strip()
            if not filename: return
        download_thread = threading.Thread(target=self.download_file_worker, args=(filename,), daemon=True)
        download_thread.start()

    def download_file_worker(self, filename):
        try:
            server_ip = self.client_ip.GetValue()
            server_port = int(self.client_port.GetValue())

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                self.log_client(f"Connecting to {server_ip}:{server_port} for download...")
                client_socket.connect((server_ip, server_port))
                client_socket.sendall(b"DNLD")
                filename_bytes = filename.encode('utf-8')
                client_socket.sendall(struct.pack('!I', len(filename_bytes)))
                client_socket.sendall(filename_bytes)
                file_size_data = self.receive_exactly(client_socket, 8)
                file_size = struct.unpack('!Q', file_size_data)[0]
                if file_size == 0:
                    self.log_client(f"File not found on server: {filename}")
                    return
                self.log_client(f"Downloading {filename} ({file_size} bytes)")
                filepath = os.path.join(self.client_downloads_dir, filename)
                with open(filepath, 'wb') as f:
                    received_bytes = 0
                    while received_bytes < file_size:
                        chunk_size = min(self.buffer_size, file_size - received_bytes)
                        chunk = self.receive_exactly(client_socket, chunk_size)
                        if not chunk: break
                        f.write(chunk)
                        received_bytes += len(chunk)
                self.log_client(f"Download successful: {filename}")
        except Exception as e:
            self.log_client(f"Download error: {str(e)}")

    def on_close(self, event):
        if self.is_server_running:
            self.stop_server()
        self.Destroy()


if __name__ == '__main__':
    app = wx.App(False)
    frame = FileTransferApp()
    frame.Show()
    app.MainLoop()