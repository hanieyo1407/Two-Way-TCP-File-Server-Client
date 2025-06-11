import wx
import wx.lib.embeddedimage
import socket
import threading
import os
import struct
import time


class FileTransferApp(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Vibrant TCP File Transfer", size=(650, 600))

        self.BG_COLOR = '#2B2B2B'
        self.TEXT_COLOR = '#BBBBBB'
        self.INPUT_BG_COLOR = '#3C3F41'
        self.ACCENT_COLOR = '#4EAA52'
        self.SUCCESS_COLOR = '#52A355'
        self.ERROR_COLOR = '#D9534F'
        self.INFO_COLOR = '#5BC0DE'

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
        panel.SetBackgroundColour(self.BG_COLOR)
        panel.SetForegroundColour(self.TEXT_COLOR)

        main_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Arial")
        bold_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Arial")
        log_font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        panel.SetFont(main_font)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        server_box = wx.StaticBox(panel, label="Server Mode")
        server_box.SetForegroundColour(self.ACCENT_COLOR)
        server_box.SetFont(bold_font)
        server_sizer = wx.StaticBoxSizer(server_box, wx.VERTICAL)

        server_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        server_controls_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALL | wx.CENTER, 5)
        self.server_port = wx.TextCtrl(panel, value="65432", size=(80, -1))
        self.server_port.SetBackgroundColour(self.INPUT_BG_COLOR)
        self.server_port.SetForegroundColour(self.TEXT_COLOR)
        server_controls_sizer.Add(self.server_port, 0, wx.ALL, 5)
        self.server_btn = wx.Button(panel, label="Start Server")
        self.server_btn.Bind(wx.EVT_BUTTON, self.on_server_toggle)
        server_controls_sizer.Add(self.server_btn, 0, wx.ALL, 5)
        server_sizer.Add(server_controls_sizer, 0, wx.ALL, 5)
        self.server_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.server_status.SetFont(log_font)
        self.server_status.SetBackgroundColour(self.INPUT_BG_COLOR)
        server_sizer.Add(self.server_status, 1, wx.ALL | wx.EXPAND, 5)

        client_box = wx.StaticBox(panel, label="Client Mode")
        client_box.SetForegroundColour(self.ACCENT_COLOR)
        client_box.SetFont(bold_font)
        client_sizer = wx.StaticBoxSizer(client_box, wx.VERTICAL)

        connection_sizer = wx.FlexGridSizer(2, 2, 5, 5)
        connection_sizer.AddGrowableCol(1, 1)
        connection_sizer.Add(wx.StaticText(panel, label="Server IP:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.client_ip = wx.TextCtrl(panel, value="127.0.0.1")
        self.client_ip.SetBackgroundColour(self.INPUT_BG_COLOR)
        self.client_ip.SetForegroundColour(self.TEXT_COLOR)
        connection_sizer.Add(self.client_ip, 1, wx.EXPAND)
        connection_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.client_port = wx.TextCtrl(panel, value="65432")
        self.client_port.SetBackgroundColour(self.INPUT_BG_COLOR)
        self.client_port.SetForegroundColour(self.TEXT_COLOR)
        connection_sizer.Add(self.client_port, 1, wx.EXPAND)
        client_sizer.Add(connection_sizer, 0, wx.EXPAND | wx.ALL, 5)

        transfer_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.upload_btn = wx.Button(panel, label="  Upload File")
        self.upload_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_UP, wx.ART_BUTTON))
        self.upload_btn.Bind(wx.EVT_BUTTON, self.on_upload_file)
        transfer_sizer.Add(self.upload_btn, 1, wx.ALL | wx.EXPAND, 5)
        self.download_btn = wx.Button(panel, label="  Download File")
        self.download_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_BUTTON))
        self.download_btn.Bind(wx.EVT_BUTTON, self.on_download_file)
        transfer_sizer.Add(self.download_btn, 1, wx.ALL | wx.EXPAND, 5)
        client_sizer.Add(transfer_sizer, 0, wx.EXPAND | wx.ALL, 0)

        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.progress_bar.Hide()
        client_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 5)

        self.client_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.client_status.SetFont(log_font)
        self.client_status.SetBackgroundColour(self.INPUT_BG_COLOR)
        client_sizer.Add(self.client_status, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(server_sizer, 1, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(client_sizer, 1, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(main_sizer)

    def log_server(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.server_status, message, log_type)

    def log_client(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.client_status, message, log_type)

    def _append_to_textctrl(self, textctrl, message, log_type):
        color_map = {'info': self.INFO_COLOR, 'success': self.SUCCESS_COLOR, 'error': self.ERROR_COLOR}
        color = color_map.get(log_type, self.TEXT_COLOR)

        timestamp = f"[{time.strftime('%H:%M:%S')}] "
        textctrl.SetDefaultStyle(wx.TextAttr(self.TEXT_COLOR))
        textctrl.AppendText(timestamp)

        textctrl.SetDefaultStyle(wx.TextAttr(color))
        textctrl.AppendText(f"{message}\n")
        textctrl.SetDefaultStyle(wx.TextAttr(self.TEXT_COLOR))

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
            self.log_server(f"Server started on port {port}. Listening...", 'success')
            self.server_thread = threading.Thread(target=self.server_worker, daemon=True)
            self.server_thread.start()
        except Exception as e:
            self.log_server(f"Error starting server: {str(e)}", 'error')

    def stop_server(self):
        self.is_server_running = False
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        self.server_btn.SetLabel("Start Server")
        self.server_port.Enable()
        self.log_server("Server stopped.", 'info')

    def server_worker(self):
        while self.is_server_running:
            try:
                client_socket, client_address = self.server_socket.accept()
                self.log_server(f"Accepted connection from: {client_address}", 'info')
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address),
                                                 daemon=True)
                client_thread.start()
            except (OSError, ConnectionAbortedError):
                break
            except Exception as e:
                if self.is_server_running:
                    self.log_server(f"Server error: {str(e)}", 'error')
                break

    def handle_client(self, client_socket, client_address):
        try:
            command_data = self.receive_exactly(client_socket, 4)
            if not command_data: return
            command = command_data.decode('utf-8').strip()
            self.log_server(f"Received command: {command} from {client_address}", 'info')
            if command == "UPLD":
                self.handle_upload(client_socket, client_address)
            elif command == "DNLD":
                self.handle_download(client_socket, client_address)
            else:
                self.log_server(f"Unknown command: {command}", 'error')
        except Exception as e:
            self.log_server(f"Error handling client {client_address}: {str(e)}", 'error')
        finally:
            client_socket.close()
            self.log_server(f"Client {client_address} disconnected.", 'info')

    def handle_upload(self, client_socket, client_address):
        try:
            filename_length_data = self.receive_exactly(client_socket, 4)
            filename_length = struct.unpack('!I', filename_length_data)[0]
            filename_data = self.receive_exactly(client_socket, filename_length)
            filename = filename_data.decode('utf-8')
            file_size_data = self.receive_exactly(client_socket, 8)
            file_size = struct.unpack('!Q', file_size_data)[0]
            self.log_server(f"Receiving file: {filename} ({file_size} bytes)", 'info')
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
            self.log_server(f"File '{filename}' uploaded successfully.", 'success')
        except Exception as e:
            self.log_server(f"Error during upload: {str(e)}", 'error')
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
            self.log_server(f"Download request for: {filename}", 'info')
            filepath = os.path.join(self.server_uploads_dir, filename)
            if not os.path.exists(filepath):
                client_socket.sendall(struct.pack('!Q', 0))
                self.log_server(f"File not found: {filename}", 'error')
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
            self.log_server(f"File '{filename}' sent successfully.", 'success')
        except Exception as e:
            self.log_server(f"Error during download: {str(e)}", 'error')

    def receive_exactly(self, sock, num_bytes):
        data = b''
        while len(data) < num_bytes:
            chunk = sock.recv(num_bytes - len(data))
            if not chunk: return None
            data += chunk
        return data

    def update_progress(self, value, show=True):
        wx.CallAfter(self._update_progress_ui, value, show)

    def _update_progress_ui(self, value, show):
        if show:
            self.progress_bar.SetValue(value)
            if not self.progress_bar.IsShown():
                self.progress_bar.Show()
                self.Layout()
        else:
            self.progress_bar.Hide()
            self.Layout()

    def set_client_buttons_enabled(self, enabled=True):
        self.upload_btn.Enable(enabled)
        self.download_btn.Enable(enabled)

    def on_upload_file(self, event):
        with wx.FileDialog(self, "Choose file to upload", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL: return
            filepath = fileDialog.GetPath()
        upload_thread = threading.Thread(target=self.upload_file_worker, args=(filepath,), daemon=True)
        upload_thread.start()

    def upload_file_worker(self, filepath):
        self.set_client_buttons_enabled(False)
        self.update_progress(0, show=True)
        try:
            server_ip = self.client_ip.GetValue()
            server_port = int(self.client_port.GetValue())
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                self.log_client(f"Connecting to {server_ip}:{server_port}...", 'info')
                client_socket.connect((server_ip, server_port))
                client_socket.sendall(b"UPLD")
                filename_bytes = filename.encode('utf-8')
                client_socket.sendall(struct.pack('!I', len(filename_bytes)))
                client_socket.sendall(filename_bytes)
                client_socket.sendall(struct.pack('!Q', file_size))
                self.log_client(f"Uploading {filename} ({file_size} bytes)", 'info')
                with open(filepath, 'rb') as f:
                    sent_bytes = 0
                    while sent_bytes < file_size:
                        chunk = f.read(self.buffer_size)
                        if not chunk: break
                        client_socket.sendall(chunk)
                        sent_bytes += len(chunk)
                        progress = int((sent_bytes / file_size) * 100)
                        self.update_progress(progress)
                response = client_socket.recv(1024)
                if response == b"OK":
                    self.log_client(f"Upload successful: {filename}", 'success')
                else:
                    self.log_client(f"Upload failed: {response.decode()}", 'error')
        except Exception as e:
            self.log_client(f"Upload error: {str(e)}", 'error')
        finally:
            self.update_progress(0, show=False)
            self.set_client_buttons_enabled(True)

    def on_download_file(self, event):
        with wx.TextEntryDialog(self, "Enter filename to download from the server:", "Download File",
                                style=wx.OK | wx.CANCEL) as dialog:
            dialog.SetBackgroundColour(self.BG_COLOR)
            dialog.GetChildren()[0].SetForegroundColour(self.TEXT_COLOR)  # The message
            dialog.GetChildren()[1].SetBackgroundColour(self.INPUT_BG_COLOR)  # The text input
            dialog.GetChildren()[1].SetForegroundColour(self.TEXT_COLOR)
            if dialog.ShowModal() == wx.ID_CANCEL: return
            filename = dialog.GetValue().strip()
            if not filename: return
        download_thread = threading.Thread(target=self.download_file_worker, args=(filename,), daemon=True)
        download_thread.start()

    def download_file_worker(self, filename):
        self.set_client_buttons_enabled(False)
        self.update_progress(0, show=True)
        try:
            server_ip = self.client_ip.GetValue()
            server_port = int(self.client_port.GetValue())
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                self.log_client(f"Connecting to {server_ip}:{server_port}...", 'info')
                client_socket.connect((server_ip, server_port))
                client_socket.sendall(b"DNLD")
                filename_bytes = filename.encode('utf-8')
                client_socket.sendall(struct.pack('!I', len(filename_bytes)))
                client_socket.sendall(filename_bytes)
                file_size_data = self.receive_exactly(client_socket, 8)
                file_size = struct.unpack('!Q', file_size_data)[0]
                if file_size == 0:
                    self.log_client(f"File not found on server: {filename}", 'error')
                    return
                self.log_client(f"Downloading {filename} ({file_size} bytes)", 'info')
                filepath = os.path.join(self.client_downloads_dir, filename)
                with open(filepath, 'wb') as f:
                    received_bytes = 0
                    while received_bytes < file_size:
                        chunk_size = min(self.buffer_size, file_size - received_bytes)
                        chunk = self.receive_exactly(client_socket, chunk_size)
                        if not chunk: break
                        f.write(chunk)
                        received_bytes += len(chunk)
                        progress = int((received_bytes / file_size) * 100)
                        self.update_progress(progress)
                self.log_client(f"Download successful: {filename}", 'success')
        except Exception as e:
            self.log_client(f"Download error: {str(e)}", 'error')
        finally:
            self.update_progress(0, show=False)
            self.set_client_buttons_enabled(True)

    def on_close(self, event):
        if self.is_server_running:
            self.stop_server()
        self.Destroy()


if __name__ == '__main__':
    app = wx.App(False)
    frame = FileTransferApp()
    frame.Show()
    app.MainLoop()