import wx
import socket
import threading
import os
import struct
import time
import ssl
import configparser


# --- Drag and Drop Class ---
class FileDropTarget(wx.FileDropTarget):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def OnDropFiles(self, x, y, filenames):
        if self.window.upload_btn.IsEnabled() and filenames:
            filepath = filenames[0]  # Handle the first dropped file
            self.window.log_client(f"File dropped: {os.path.basename(filepath)}. Starting upload.", 'info')
            threading.Thread(target=self.window.upload_file_worker, args=(filepath,), daemon=True).start()
            return True
        return False


class FileTransferApp(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Pro File Transfer Suite", size=(700, 700))

        # --- Color Scheme & Config ---
        self.BG_COLOR = '#2C3E50';
        self.TEXT_COLOR = '#ECF0F1';
        self.INPUT_BG_COLOR = '#34495E'
        self.ACCENT_COLOR = '#1ABC9C';
        self.SUCCESS_COLOR = '#2ECC71';
        self.ERROR_COLOR = '#E74C3C'
        self.INFO_COLOR = '#3498DB';
        self.server_socket = None;
        self.server_thread = None
        self.is_server_running = False;
        self.buffer_size = 8192  # Increased buffer size for better performance
        self.server_uploads_dir = "server_uploads";
        self.client_downloads_dir = "client_downloads"
        self.config_file = 'config.ini'

        os.makedirs(self.server_uploads_dir, exist_ok=True)
        os.makedirs(self.client_downloads_dir, exist_ok=True)

        self.CreateStatusBar()
        self.SetStatusText("Ready")

        self.config = self.load_config()
        self.create_gui()
        self.Center()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    # --- Config, Logging and UI Helper Methods ---
    def load_config(self):
        config = configparser.ConfigParser();
        config.read(self.config_file)
        if 'Client' not in config: config['Client'] = {}
        if 'Server' not in config: config['Server'] = {}
        return config

    def save_config(self):
        self.config['Client']['ip'] = self.client_ip.GetValue();
        self.config['Client']['port'] = self.client_port.GetValue()
        self.config['Client']['ssl'] = str(self.use_ssl_client.GetValue());
        self.config['Server']['port'] = self.server_port.GetValue()
        self.config['Server']['ssl'] = str(self.use_ssl_server.GetValue())
        with open(self.config_file, 'w') as configfile: self.config.write(configfile)

    def format_speed(self, speed_bytes_per_sec):
        if speed_bytes_per_sec < 1024:
            return f"{speed_bytes_per_sec:.2f} B/s"
        elif speed_bytes_per_sec < 1024 ** 2:
            return f"{speed_bytes_per_sec / 1024:.2f} KB/s"
        elif speed_bytes_per_sec < 1024 ** 3:
            return f"{speed_bytes_per_sec / 1024 ** 2:.2f} MB/s"
        else:
            return f"{speed_bytes_per_sec / 1024 ** 3:.2f} GB/s"

    def format_eta(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"

    def create_gui(self):
        panel = wx.Panel(self);
        panel.SetBackgroundColour(self.BG_COLOR);
        panel.SetForegroundColour(self.TEXT_COLOR)
        drop_target = FileDropTarget(self);
        panel.SetDropTarget(drop_target)  # Enable Drag and Drop

        main_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Segoe UI")
        bold_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Segoe UI")
        log_font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Consolas")

        panel.SetFont(main_font);
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        # --- GUI definition remains the same as last version ---
        # --- Server Section ---
        server_box = wx.StaticBox(panel, label="Server Mode");
        server_box.SetForegroundColour(self.ACCENT_COLOR);
        server_box.SetFont(bold_font)
        server_sizer = wx.StaticBoxSizer(server_box, wx.VERTICAL)
        server_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        server_controls_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALL | wx.CENTER, 5)
        server_port_val = self.config.get('Server', 'port', fallback='65432')
        self.server_port = wx.TextCtrl(panel, value=server_port_val, size=(80, -1))
        self.server_port.SetBackgroundColour(self.INPUT_BG_COLOR);
        self.server_port.SetForegroundColour(self.TEXT_COLOR)
        server_controls_sizer.Add(self.server_port, 0, wx.ALL, 5)
        use_ssl_server_val = self.config.getboolean('Server', 'ssl', fallback=True)
        self.use_ssl_server = wx.CheckBox(panel, label="Use SSL/TLS");
        self.use_ssl_server.SetValue(use_ssl_server_val)
        server_controls_sizer.Add(self.use_ssl_server, 0, wx.ALL | wx.CENTER, 5)
        self.server_btn = wx.Button(panel, label="Start Server");
        self.server_btn.SetToolTip("Start or stop the file server.")
        self.server_btn.Bind(wx.EVT_BUTTON, self.on_server_toggle)
        server_controls_sizer.Add(self.server_btn, 0, wx.ALL, 5)
        server_sizer.Add(server_controls_sizer, 0, wx.ALL | wx.EXPAND, 5)
        self.server_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.server_status.SetFont(log_font);
        self.server_status.SetBackgroundColour(self.INPUT_BG_COLOR)
        server_sizer.Add(self.server_status, 1, wx.ALL | wx.EXPAND, 5)
        # --- Client Section ---
        client_box = wx.StaticBox(panel, label="Client Mode");
        client_box.SetForegroundColour(self.ACCENT_COLOR);
        client_box.SetFont(bold_font)
        client_sizer = wx.StaticBoxSizer(client_box, wx.VERTICAL)
        connection_sizer = wx.FlexGridSizer(3, 2, 5, 5);
        connection_sizer.AddGrowableCol(1, 1)
        connection_sizer.Add(wx.StaticText(panel, label="Server IP:"), 0, wx.ALIGN_CENTER_VERTICAL)
        client_ip_val = self.config.get('Client', 'ip', fallback='127.0.0.1')
        self.client_ip = wx.TextCtrl(panel, value=client_ip_val)
        self.client_ip.SetBackgroundColour(self.INPUT_BG_COLOR);
        self.client_ip.SetForegroundColour(self.TEXT_COLOR)
        connection_sizer.Add(self.client_ip, 1, wx.EXPAND)
        connection_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL)
        client_port_val = self.config.get('Client', 'port', fallback='65432')
        self.client_port = wx.TextCtrl(panel, value=client_port_val)
        self.client_port.SetBackgroundColour(self.INPUT_BG_COLOR);
        self.client_port.SetForegroundColour(self.TEXT_COLOR)
        connection_sizer.Add(self.client_port, 1, wx.EXPAND)
        connection_sizer.AddSpacer(0)
        use_ssl_client_val = self.config.getboolean('Client', 'ssl', fallback=True)
        self.use_ssl_client = wx.CheckBox(panel, label="Use SSL/TLS");
        self.use_ssl_client.SetValue(use_ssl_client_val)
        connection_sizer.Add(self.use_ssl_client, 0, wx.ALL | wx.CENTER, 0)
        client_sizer.Add(connection_sizer, 0, wx.EXPAND | wx.ALL, 5)
        upload_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.upload_btn = wx.Button(panel, label="Upload File to Server")
        self.upload_btn.SetToolTip("Select a local file to send to the server.")
        self.upload_btn.Bind(wx.EVT_BUTTON, self.on_upload_file)
        upload_sizer.Add(self.upload_btn, 1, wx.EXPAND | wx.ALL, 5)
        client_sizer.Add(upload_sizer, 0, wx.EXPAND)
        download_box = wx.StaticBox(panel, label="Download from Server");
        download_box.SetForegroundColour(self.TEXT_COLOR)
        download_sizer = wx.StaticBoxSizer(download_box, wx.VERTICAL)
        self.remote_files = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.remote_files.SetBackgroundColour(self.INPUT_BG_COLOR);
        self.remote_files.SetForegroundColour(self.TEXT_COLOR)
        download_sizer.Add(self.remote_files, 1, wx.EXPAND | wx.ALL, 5)
        download_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label="Refresh List")
        self.refresh_btn.SetToolTip("Get an updated list of files from the server.")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh_list)
        download_buttons_sizer.Add(self.refresh_btn, 1, wx.EXPAND | wx.ALL, 5)
        self.download_btn = wx.Button(panel, label="Download Selected")
        self.download_btn.SetToolTip("Download the file currently selected in the list.")
        self.download_btn.Bind(wx.EVT_BUTTON, self.on_download_file)
        download_buttons_sizer.Add(self.download_btn, 1, wx.EXPAND | wx.ALL, 5)
        download_sizer.Add(download_buttons_sizer, 0, wx.EXPAND)
        client_sizer.Add(download_sizer, 1, wx.EXPAND | wx.ALL, 5)
        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.progress_bar.Hide()
        client_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 5)
        self.client_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.client_status.SetFont(log_font);
        self.client_status.SetBackgroundColour(self.INPUT_BG_COLOR)

        client_sizer.Add(self.client_status, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(server_sizer, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(client_sizer, 1, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(main_sizer)
        drag_drop_label = wx.StaticText(panel, label="©HANIEYO1407.Tec")
        drag_drop_label.SetForegroundColour(self.INFO_COLOR)
        client_sizer.Add(drag_drop_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

    # All backend and handler methods are the same as before, but the worker threads are modified for live status updates.
    def log_server(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.server_status, message, log_type)

    def log_client(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.client_status, message, log_type)

    def _append_to_textctrl(self, textctrl, message, log_type):
        color_map = {'info': self.INFO_COLOR, 'success': self.SUCCESS_COLOR, 'error': self.ERROR_COLOR};
        color = color_map.get(log_type, self.TEXT_COLOR)
        timestamp = f"[{time.strftime('%H:%M:%S')}] ";
        textctrl.SetDefaultStyle(wx.TextAttr(self.TEXT_COLOR));
        textctrl.AppendText(timestamp)
        textctrl.SetDefaultStyle(wx.TextAttr(color));
        textctrl.AppendText(f"{message}\n");
        textctrl.SetDefaultStyle(wx.TextAttr(self.TEXT_COLOR))

    def update_progress(self, value, show=True):
        wx.CallAfter(self._update_progress_ui, value, show)

    def _update_progress_ui(self, value, show):
        if show:
            self.progress_bar.SetValue(value)
            if not self.progress_bar.IsShown(): self.progress_bar.Show(); self.Layout()
        else:
            if self.progress_bar.IsShown(): self.progress_bar.Hide(); self.Layout()

    def set_client_controls_enabled(self, enabled=True):
        self.upload_btn.Enable(enabled);
        self.download_btn.Enable(enabled);
        self.refresh_btn.Enable(enabled)
        self.client_ip.Enable(enabled);
        self.client_port.Enable(enabled);
        self.use_ssl_client.Enable(enabled)

    def on_server_toggle(self, event):
        if not self.is_server_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        try:
            port = int(self.server_port.GetValue());
            use_ssl = self.use_ssl_server.GetValue()
            if use_ssl and (not os.path.exists('cert.pem') or not os.path.exists('key.pem')):
                self.log_server("cert.pem or key.pem not found for SSL. Please generate them.", 'error');
                return
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port));
            self.server_socket.listen(5);
            self.is_server_running = True;
            self.server_btn.SetLabel("Stop Server")
            self.server_port.Disable();
            self.use_ssl_server.Disable();
            self.log_server(f"Server started on port {port} (SSL: {'On' if use_ssl else 'Off'})...", 'success')
            self.server_thread = threading.Thread(target=self.server_worker, args=(use_ssl,), daemon=True);
            self.server_thread.start()
        except Exception as e:
            self.log_server(f"Error starting server: {str(e)}", 'error')

    def stop_server(self):
        self.is_server_running = False
        if self.server_socket: self.server_socket.close(); self.server_socket = None
        self.server_btn.SetLabel("Start Server");
        self.server_port.Enable();
        self.use_ssl_server.Enable();
        self.log_server("Server stopped.", 'info')

    def server_worker(self, use_ssl):
        ssl_context = None
        if use_ssl: ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH); ssl_context.load_cert_chain(
            certfile='cert.pem', keyfile='key.pem')
        while self.is_server_running:
            try:
                conn, addr = self.server_socket.accept()
                if use_ssl: conn = ssl_context.wrap_socket(conn, server_side=True)
                self.log_server(f"Accepted connection from: {addr}", 'info');
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True);
                client_thread.start()
            except (OSError, ConnectionAbortedError, ssl.SSLError):
                break
            except Exception as e:
                if self.is_server_running: self.log_server(f"Server error: {str(e)}", 'error')
                break

    def handle_client(self, conn, addr):
        try:
            command_data = self.receive_exactly(conn, 4)
            if not command_data: return
            command = command_data.decode('utf-8').strip();
            self.log_server(f"Received command: {command} from {addr}", 'info')
            if command == "UPLD":
                self.handle_upload(conn)
            elif command == "DNLD":
                self.handle_download(conn)
            elif command == "LIST":
                self.handle_list(conn)
            else:
                self.log_server(f"Unknown command: {command}", 'error')
        except Exception as e:
            self.log_server(f"Error handling client {addr}: {str(e)}", 'error')
        finally:
            conn.close(); self.log_server(f"Client {addr} disconnected.", 'info')

    def handle_list(self, conn):
        self.log_server("Sending file list.", 'info');
        files = os.listdir(self.server_uploads_dir);
        file_list_str = "\n".join(files);
        conn.sendall(file_list_str.encode('utf-8'))

    def handle_upload(self, conn):
        try:
            filename_len = struct.unpack('!I', self.receive_exactly(conn, 4))[0];
            filename = self.receive_exactly(conn, filename_len).decode('utf-8')
            file_size = struct.unpack('!Q', self.receive_exactly(conn, 8))[0];
            self.log_server(f"Receiving file: {filename} ({file_size} bytes)", 'info')
            filepath = os.path.join(self.server_uploads_dir, os.path.basename(filename))
            with open(filepath, 'wb') as f:
                received = 0
                while received < file_size:
                    chunk = self.receive_exactly(conn, min(self.buffer_size, file_size - received));
                    if not chunk: break
                    f.write(chunk);
                    received += len(chunk)
            conn.sendall(b"OK");
            self.log_server(f"File '{filename}' uploaded successfully.", 'success')
        except Exception as e:
            self.log_server(f"Error during upload: {str(e)}", 'error')
            try:
                conn.sendall(b"ERROR")
            except:
                pass

    def handle_download(self, conn):
        try:
            filename_len = struct.unpack('!I', self.receive_exactly(conn, 4))[0];
            filename = self.receive_exactly(conn, filename_len).decode('utf-8')
            self.log_server(f"Download request for: {filename}", 'info');
            filepath = os.path.join(self.server_uploads_dir, os.path.basename(filename))
            if not os.path.exists(filepath): conn.sendall(struct.pack('!Q', 0)); return
            file_size = os.path.getsize(filepath);
            conn.sendall(struct.pack('!Q', file_size))
            with open(filepath, 'rb') as f:
                conn.sendfile(f)
            self.log_server(f"File '{filename}' sent successfully.", 'success')
        except Exception as e:
            self.log_server(f"Error during download: {str(e)}", 'error')

    def receive_exactly(self, sock, num_bytes):
        data = bytearray(num_bytes);
        mv = memoryview(data);
        bytes_recvd = 0
        while bytes_recvd < num_bytes:
            chunk_size = sock.recv_into(mv[bytes_recvd:], num_bytes - bytes_recvd)
            if chunk_size == 0: return None
            bytes_recvd += chunk_size
        return data

    def on_refresh_list(self, event):
        threading.Thread(target=self.refresh_list_worker, daemon=True).start()

    def refresh_list_worker(self):
        wx.CallAfter(self.set_client_controls_enabled, False);
        wx.CallAfter(self.SetStatusText, "Refreshing list...")
        try:
            ip, port, use_ssl = self.client_ip.GetValue(), int(
                self.client_port.GetValue()), self.use_ssl_client.GetValue()
            with socket.create_connection((ip, port)) as sock:
                conn = sock
                if use_ssl: context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE; conn = context.wrap_socket(
                    sock, server_hostname=ip)
                conn.sendall(b'LIST');
                file_list_str = conn.recv(4096).decode('utf-8');
                files = file_list_str.split('\n') if file_list_str else []
                wx.CallAfter(self.remote_files.Set, files);
                self.log_client("Refreshed server file list.", 'success');
                wx.CallAfter(self.SetStatusText, "List refreshed.")
        except Exception as e:
            self.log_client(f"Failed to get file list: {e}", 'error'); wx.CallAfter(self.SetStatusText,
                                                                                    "Failed to refresh list.")
        finally:
            wx.CallAfter(self.set_client_controls_enabled, True)

    def on_upload_file(self, event):
        with wx.FileDialog(self, "Choose file to upload", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            filepath = dlg.GetPath()
        threading.Thread(target=self.upload_file_worker, args=(filepath,), daemon=True).start()

    def upload_file_worker(self, filepath):
        wx.CallAfter(self.set_client_controls_enabled, False);
        self.update_progress(0, True)
        try:
            ip, port, use_ssl = self.client_ip.GetValue(), int(
                self.client_port.GetValue()), self.use_ssl_client.GetValue()
            filename, file_size = os.path.basename(filepath), os.path.getsize(filepath)
            with socket.create_connection((ip, port)) as sock:
                conn = sock
                if use_ssl: context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE; conn = context.wrap_socket(
                    sock, server_hostname=ip)
                self.log_client(f"Uploading {filename} ({file_size} bytes)...", 'info');
                conn.sendall(b'UPLD');
                conn.sendall(struct.pack('!I', len(filename)) + filename.encode('utf-8'));
                conn.sendall(struct.pack('!Q', file_size))
                with open(filepath, 'rb') as f:
                    sent = 0;
                    start_time = time.time();
                    last_update_time = start_time
                    while sent < file_size:
                        data = f.read(self.buffer_size);
                        if not data: break
                        conn.sendall(data);
                        sent += len(data);
                        self.update_progress(int((sent / file_size) * 100))
                        current_time = time.time()
                        if current_time - last_update_time > 0.25:
                            elapsed_time = current_time - start_time;
                            speed = sent / elapsed_time if elapsed_time > 0 else 0
                            eta = ((file_size - sent) / speed) if speed > 0 else 0
                            wx.CallAfter(self.SetStatusText,
                                         f"Uploading at {self.format_speed(speed)} | ETA: {self.format_eta(eta)}")
                            last_update_time = current_time
                if conn.recv(2) == b"OK":
                    self.log_client(f"Upload successful: {filename}", 'success'); wx.CallAfter(self.SetStatusText,
                                                                                               "Upload complete.")
                else:
                    self.log_client(f"Upload failed for {filename}.", 'error'); wx.CallAfter(self.SetStatusText,
                                                                                             "Upload failed.")
        except Exception as e:
            self.log_client(f"Upload error: {e}", 'error'); wx.CallAfter(self.SetStatusText, "Upload error.")
        finally:
            self.update_progress(0, False); wx.CallAfter(self.set_client_controls_enabled, True)

    def on_download_file(self, event):
        selected_index = self.remote_files.GetSelection()
        if selected_index == wx.NOT_FOUND: wx.MessageBox("Please select a file from the list to download.",
                                                         "No File Selected", wx.OK | wx.ICON_INFORMATION); return
        filename = self.remote_files.GetString(selected_index)
        threading.Thread(target=self.download_file_worker, args=(filename,), daemon=True).start()

    def download_file_worker(self, filename):
        wx.CallAfter(self.set_client_controls_enabled, False);
        self.update_progress(0, True)
        try:
            ip, port, use_ssl = self.client_ip.GetValue(), int(
                self.client_port.GetValue()), self.use_ssl_client.GetValue()
            with socket.create_connection((ip, port)) as sock:
                conn = sock
                if use_ssl: context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE; conn = context.wrap_socket(
                    sock, server_hostname=ip)
                conn.sendall(b'DNLD');
                conn.sendall(struct.pack('!I', len(filename)) + filename.encode('utf-8'))
                file_size = struct.unpack('!Q', self.receive_exactly(conn, 8))[0]
                if file_size == 0: self.log_client(f"File not found on server: {filename}", 'error'); wx.CallAfter(
                    self.SetStatusText, "File not found."); return
                self.log_client(f"Downloading {filename} ({file_size} bytes)...", 'info');
                filepath = os.path.join(self.client_downloads_dir, filename)
                with open(filepath, 'wb') as f:
                    received = 0;
                    start_time = time.time();
                    last_update_time = start_time
                    while received < file_size:
                        chunk = self.receive_exactly(conn, min(self.buffer_size, file_size - received));
                        if not chunk: break
                        f.write(chunk);
                        received += len(chunk);
                        self.update_progress(int((received / file_size) * 100))
                        current_time = time.time()
                        if current_time - last_update_time > 0.25:
                            elapsed_time = current_time - start_time;
                            speed = received / elapsed_time if elapsed_time > 0 else 0
                            eta = ((file_size - received) / speed) if speed > 0 else 0
                            wx.CallAfter(self.SetStatusText,
                                         f"Downloading at {self.format_speed(speed)} | ETA: {self.format_eta(eta)}")
                            last_update_time = current_time
                self.log_client(f"Download successful: {filename}", 'success');
                wx.CallAfter(self.SetStatusText, "Download complete.")
        except Exception as e:
            self.log_client(f"Download error: {e}", 'error'); wx.CallAfter(self.SetStatusText, "Download error.")
        finally:
            self.update_progress(0, False); wx.CallAfter(self.set_client_controls_enabled, True)

    def on_close(self, event):
        self.save_config();
        if self.is_server_running: self.stop_server()
        self.Destroy()


if __name__ == '__main__':
    app = wx.App(False)
    frame = FileTransferApp()
    frame.Show()
    app.MainLoop()