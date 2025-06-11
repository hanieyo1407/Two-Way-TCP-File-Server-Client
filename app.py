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
            filepath = filenames[0]
            self.window.log_client(f"File dropped: {os.path.basename(filepath)}. Starting upload.", 'info')
            threading.Thread(target=self.window.upload_file_worker, args=(filepath,), daemon=True).start()
            return True
        return False


class FileTransferApp(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Pro File Transfer Suite", size=(700, 700))

        # --- Centralized Theme Definitions ---
        self.themes = {
            'dark': {
                'BG_COLOR': '#2C3E50', 'TEXT_COLOR': '#ECF0F1', 'INPUT_BG_COLOR': '#34495E',
                'ACCENT_COLOR': '#1ABC9C', 'SUCCESS_COLOR': '#2ECC71', 'ERROR_COLOR': '#E74C3C',
                'INFO_COLOR': '#3498DB', 'STATIC_BOX_TEXT': '#ECF0F1'
            },
            'light': {
                'BG_COLOR': '#ECF0F1', 'TEXT_COLOR': '#2C3E50', 'INPUT_BG_COLOR': '#FFFFFF',
                'ACCENT_COLOR': '#2980B9', 'SUCCESS_COLOR': '#27AE60', 'ERROR_COLOR': '#C0392B',
                'INFO_COLOR': '#2980B9', 'STATIC_BOX_TEXT': '#2C3E50'
            }
        }

        self.server_socket = None;
        self.server_thread = None;
        self.is_server_running = False
        self.buffer_size = 8192;
        self.server_uploads_dir = "server_uploads";
        self.client_downloads_dir = "client_downloads"
        self.config_file = 'config.ini'

        os.makedirs(self.server_uploads_dir, exist_ok=True)
        os.makedirs(self.client_downloads_dir, exist_ok=True)

        self.CreateStatusBar()
        self.config = self.load_config()
        self.mode = self.config.get('UI', 'mode', fallback='dark')

        self.create_gui()
        self.apply_theme()
        self.Center()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def load_config(self):
        config = configparser.ConfigParser();
        config.read(self.config_file)
        if 'Client' not in config: config['Client'] = {}
        if 'Server' not in config: config['Server'] = {}
        if 'UI' not in config: config['UI'] = {}
        return config

    def save_config(self):
        self.config['Client']['ip'] = self.client_ip.GetValue();
        self.config['Client']['port'] = self.client_port.GetValue()
        self.config['Client']['ssl'] = str(self.use_ssl_client.GetValue());
        self.config['Server']['port'] = self.server_port.GetValue()
        self.config['Server']['ssl'] = str(self.use_ssl_server.GetValue());
        self.config['UI']['mode'] = self.mode
        with open(self.config_file, 'w') as configfile: self.config.write(configfile)

    def apply_theme(self):
        theme = self.themes[self.mode]
        self.panel.SetBackgroundColour(theme['BG_COLOR']);
        self.panel.SetForegroundColour(theme['TEXT_COLOR'])

        for widget in self.panel.GetChildren():
            if isinstance(widget, (wx.CheckBox, wx.StaticText)):
                widget.SetForegroundColour(theme['TEXT_COLOR'])
            if isinstance(widget, (wx.TextCtrl, wx.ListBox)):
                widget.SetBackgroundColour(theme['INPUT_BG_COLOR']);
                widget.SetForegroundColour(theme['TEXT_COLOR'])
            if isinstance(widget, wx.StaticBox):
                widget.SetForegroundColour(theme['STATIC_BOX_TEXT'])

        self.title_text.SetForegroundColour(theme['ACCENT_COLOR']);
        self.server_box.SetForegroundColour(theme['ACCENT_COLOR'])
        self.client_box.SetForegroundColour(theme['ACCENT_COLOR']);
        self.footer_text.SetForegroundColour(theme['TEXT_COLOR'])
        btn_label = "Switch to Light Mode" if self.mode == 'dark' else "Switch to Dark Mode"
        self.theme_btn.SetLabel(btn_label)
        self.panel.Refresh();
        self.Refresh()

    def create_gui(self):
        self.panel = wx.Panel(self);
        drop_target = FileDropTarget(self);
        self.panel.SetDropTarget(drop_target)
        main_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Segoe UI")
        title_font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Segoe UI")
        bold_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName="Segoe UI")
        log_font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Consolas")
        self.panel.SetFont(main_font);
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.title_text = wx.StaticText(self.panel, label="Pro File Transfer Suite");
        self.title_text.SetFont(title_font)
        title_sizer.Add(self.title_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10);
        title_sizer.AddStretchSpacer(1)
        self.theme_btn = wx.Button(self.panel);
        self.theme_btn.Bind(wx.EVT_BUTTON, self.on_toggle_theme)
        title_sizer.Add(self.theme_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5);
        main_sizer.Add(title_sizer, 0, wx.EXPAND)
        self.server_box = wx.StaticBox(self.panel, label="Server Mode");
        self.server_box.SetFont(bold_font)
        server_sizer = wx.StaticBoxSizer(self.server_box, wx.VERTICAL)
        server_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        server_controls_sizer.Add(wx.StaticText(self.panel, label="Port:"), 0, wx.ALL | wx.CENTER, 5)
        server_port_val = self.config.get('Server', 'port', fallback='65432')
        self.server_port = wx.TextCtrl(self.panel, value=server_port_val, size=(80, -1))
        server_controls_sizer.Add(self.server_port, 0, wx.ALL, 5)
        use_ssl_server_val = self.config.getboolean('Server', 'ssl', fallback=True)
        self.use_ssl_server = wx.CheckBox(self.panel, label="Use SSL/TLS");
        self.use_ssl_server.SetValue(use_ssl_server_val)
        server_controls_sizer.Add(self.use_ssl_server, 0, wx.ALL | wx.CENTER, 5)
        self.server_btn = wx.Button(self.panel, label="Start Server");
        self.server_btn.SetToolTip("Start or stop the file server.")
        self.server_btn.Bind(wx.EVT_BUTTON, self.on_server_toggle);
        server_controls_sizer.Add(self.server_btn, 0, wx.ALL, 5)
        server_sizer.Add(server_controls_sizer, 0, wx.ALL | wx.EXPAND, 5)
        self.server_status = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.server_status.SetFont(log_font);
        server_sizer.Add(self.server_status, 1, wx.ALL | wx.EXPAND, 5)
        self.client_box = wx.StaticBox(self.panel, label="Client Mode");
        self.client_box.SetFont(bold_font)
        client_sizer = wx.StaticBoxSizer(self.client_box, wx.VERTICAL)
        connection_sizer = wx.FlexGridSizer(3, 2, 5, 5);
        connection_sizer.AddGrowableCol(1, 1)
        connection_sizer.Add(wx.StaticText(self.panel, label="Server IP:"), 0, wx.ALIGN_CENTER_VERTICAL)
        client_ip_val = self.config.get('Client', 'ip', fallback='127.0.0.1');
        self.client_ip = wx.TextCtrl(self.panel, value=client_ip_val)
        connection_sizer.Add(self.client_ip, 1, wx.EXPAND)
        connection_sizer.Add(wx.StaticText(self.panel, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL)
        client_port_val = self.config.get('Client', 'port', fallback='65432');
        self.client_port = wx.TextCtrl(self.panel, value=client_port_val)
        connection_sizer.Add(self.client_port, 1, wx.EXPAND);
        connection_sizer.AddSpacer(0)
        use_ssl_client_val = self.config.getboolean('Client', 'ssl', fallback=True)
        self.use_ssl_client = wx.CheckBox(self.panel, label="Use SSL/TLS");
        self.use_ssl_client.SetValue(use_ssl_client_val)
        connection_sizer.Add(self.use_ssl_client, 0, wx.ALL | wx.CENTER, 0);
        client_sizer.Add(connection_sizer, 0, wx.EXPAND | wx.ALL, 5)
        upload_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.upload_btn = wx.Button(self.panel, label="Upload File to Server");
        self.upload_btn.SetToolTip("Select a local file or drag-drop one.")
        self.upload_btn.Bind(wx.EVT_BUTTON, self.on_upload_file);
        upload_sizer.Add(self.upload_btn, 1, wx.EXPAND | wx.ALL, 5)
        client_sizer.Add(upload_sizer, 0, wx.EXPAND)
        download_box = wx.StaticBox(self.panel, label="Download from Server")
        download_sizer = wx.StaticBoxSizer(download_box, wx.VERTICAL)
        self.remote_files = wx.ListBox(self.panel, style=wx.LB_SINGLE)
        download_sizer.Add(self.remote_files, 1, wx.EXPAND | wx.ALL, 5)
        download_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(self.panel, label="Refresh List");
        self.refresh_btn.SetToolTip("Get an updated list of files from the server.")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh_list);
        download_buttons_sizer.Add(self.refresh_btn, 1, wx.EXPAND | wx.ALL, 5)
        self.download_btn = wx.Button(self.panel, label="Download Selected");
        self.download_btn.SetToolTip("Download the file currently selected.")
        self.download_btn.Bind(wx.EVT_BUTTON, self.on_download_file);
        download_buttons_sizer.Add(self.download_btn, 1, wx.EXPAND | wx.ALL, 5)
        download_sizer.Add(download_buttons_sizer, 0, wx.EXPAND);
        client_sizer.Add(download_sizer, 1, wx.EXPAND | wx.ALL, 5)
        self.progress_bar = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL);
        self.progress_bar.Hide()
        client_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 5)
        self.client_status = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.client_status.SetFont(log_font);
        client_sizer.Add(self.client_status, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(server_sizer, 0, wx.ALL | wx.EXPAND, 10);
        main_sizer.Add(client_sizer, 1, wx.ALL | wx.EXPAND, 10)
        footer_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL)
        self.footer_text = wx.StaticText(self.panel, label="©HANIEYO1407.Tec");
        self.footer_text.SetFont(footer_font)
        main_sizer.Add(self.footer_text, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        self.panel.SetSizer(main_sizer)

    def on_toggle_theme(self, event):
        self.mode = 'light' if self.mode == 'dark' else 'dark'
        self.apply_theme()

    # --- MISSING METHODS RE-ADDED HERE ---
    def log_server(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.server_status, message, log_type)

    def log_client(self, message, log_type='info'):
        wx.CallAfter(self._append_to_textctrl, self.client_status, message, log_type)

    def _append_to_textctrl(self, textctrl, message, log_type):
        theme = self.themes[self.mode]
        color_map = {'info': theme['INFO_COLOR'], 'success': theme['SUCCESS_COLOR'], 'error': theme['ERROR_COLOR']}
        color = color_map.get(log_type, theme['TEXT_COLOR'])
        timestamp = f"[{time.strftime('%H:%M:%S')}] "
        textctrl.SetDefaultStyle(wx.TextAttr(theme['TEXT_COLOR']))
        textctrl.AppendText(timestamp)
        textctrl.SetDefaultStyle(wx.TextAttr(color))
        textctrl.AppendText(f"{message}\n")
        textctrl.SetDefaultStyle(wx.TextAttr(theme['TEXT_COLOR']))

    # --- Rest of the methods are unchanged ---
    def format_speed(self, s):
        if s < 1024:
            return f"{s:.2f} B/s"
        elif s < 1024 ** 2:
            return f"{s / 1024:.2f} KB/s"
        else:
            return f"{s / 1024 ** 2:.2f} MB/s"

    def format_eta(self, s):
        if s < 60:
            return f"{int(s)}s"
        elif s < 3600:
            return f"{int(s // 60)}m {int(s % 60)}s"
        else:
            return f"{int(s // 3600)}h {int((s % 3600) // 60)}m"

    def update_progress(self, v, s=True):
        wx.CallAfter(self._update_progress_ui, v, s)

    def _update_progress_ui(self, v, s):
        if s: self.progress_bar.SetValue(v);
        if s and not self.progress_bar.IsShown():
            self.progress_bar.Show(); self.Layout()
        elif not s and self.progress_bar.IsShown():
            self.progress_bar.Hide(); self.Layout()

    def set_client_controls_enabled(self, e=True):
        self.upload_btn.Enable(e);
        self.download_btn.Enable(e);
        self.refresh_btn.Enable(e)
        self.client_ip.Enable(e);
        self.client_port.Enable(e);
        self.use_ssl_client.Enable(e)

    def on_server_toggle(self, e):
        if not self.is_server_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        try:
            port = int(self.server_port.GetValue());
            use_ssl = self.use_ssl_server.GetValue()
            if use_ssl and (not os.path.exists('cert.pem') or not os.path.exists('key.pem')): self.log_server(
                "cert.pem or key.pem not found.", 'error'); return
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
            self.log_server(f"Error starting server: {e}", 'error')

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
            'cert.pem', 'key.pem')
        while self.is_server_running:
            try:
                conn, addr = self.server_socket.accept()
                if use_ssl: conn = ssl_context.wrap_socket(conn, server_side=True)
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True);
                client_thread.start()
            except (OSError, ssl.SSLError):
                break

    def handle_client(self, conn, addr):
        try:
            cmd = self.receive_exactly(conn, 4).decode('utf-8').strip()
            if cmd == "UPLD":
                self.handle_upload(conn)
            elif cmd == "DNLD":
                self.handle_download(conn)
            elif cmd == "LIST":
                self.handle_list(conn)
        finally:
            conn.close()

    def handle_list(self, conn):
        conn.sendall("\n".join(os.listdir(self.server_uploads_dir)).encode('utf-8'))

    def handle_upload(self, conn):
        try:
            fn_len = struct.unpack('!I', self.receive_exactly(conn, 4))[0];
            fn = self.receive_exactly(conn, fn_len).decode('utf-8')
            fs = struct.unpack('!Q', self.receive_exactly(conn, 8))[0]
            with open(os.path.join(self.server_uploads_dir, os.path.basename(fn)), 'wb') as f:
                rec, tot = 0, fs
                while rec < tot: c = self.receive_exactly(conn, min(self.buffer_size, tot - rec)); f.write(
                    c); rec += len(c)
            conn.sendall(b"OK")
        except:
            conn.sendall(b"ERROR")

    def handle_download(self, conn):
        try:
            fn_len = struct.unpack('!I', self.receive_exactly(conn, 4))[0];
            fn = self.receive_exactly(conn, fn_len).decode('utf-8')
            fp = os.path.join(self.server_uploads_dir, os.path.basename(fn))
            if not os.path.exists(fp): conn.sendall(struct.pack('!Q', 0)); return
            fs = os.path.getsize(fp);
            conn.sendall(struct.pack('!Q', fs))
            with open(fp, 'rb') as f:
                conn.sendfile(f)
        except:
            pass

    def receive_exactly(self, sock, num_bytes):
        d = bytearray(num_bytes);
        mv = memoryview(d);
        br = 0
        while br < num_bytes: c = sock.recv_into(mv[br:], num_bytes - br); br += c
        return d

    def on_refresh_list(self, e):
        threading.Thread(target=self.refresh_list_worker, daemon=True).start()

    def refresh_list_worker(self):
        wx.CallAfter(self.set_client_controls_enabled, False);
        wx.CallAfter(self.SetStatusText, "Refreshing...")
        try:
            ip, port, use_ssl = self.client_ip.GetValue(), int(
                self.client_port.GetValue()), self.use_ssl_client.GetValue()
            with socket.create_connection((ip, port)) as sock:
                conn = sock
                if use_ssl: context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE; conn = context.wrap_socket(
                    sock, server_hostname=ip)
                conn.sendall(b'LIST');
                file_list_str = conn.recv(4096).decode('utf-8');
                files = file_list_str.split('\n')
                wx.CallAfter(self.remote_files.Set, files);
                self.log_client("List refreshed.", 'success');
                wx.CallAfter(self.SetStatusText, "List refreshed.")
        except Exception as e:
            self.log_client(f"List refresh failed: {e}", 'error'); wx.CallAfter(self.SetStatusText, "Refresh failed.")
        finally:
            wx.CallAfter(self.set_client_controls_enabled, True)

    def on_upload_file(self, e):
        with wx.FileDialog(self, "Choose file", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            threading.Thread(target=self.upload_file_worker, args=(dlg.GetPath(),), daemon=True).start()

    def upload_file_worker(self, fp):
        wx.CallAfter(self.set_client_controls_enabled, False);
        self.update_progress(0, True)
        try:
            ip, port, use_ssl = self.client_ip.GetValue(), int(
                self.client_port.GetValue()), self.use_ssl_client.GetValue()
            fn, fs = os.path.basename(fp), os.path.getsize(fp)
            with socket.create_connection((ip, port)) as sock:
                conn = sock
                if use_ssl: context = ssl.create_default_context(); context.check_hostname = False; context.verify_mode = ssl.CERT_NONE; conn = context.wrap_socket(
                    sock, server_hostname=ip)
                conn.sendall(b'UPLD');
                conn.sendall(struct.pack('!I', len(fn)) + fn.encode('utf-8'));
                conn.sendall(struct.pack('!Q', fs))
                with open(fp, 'rb') as f:
                    sent, st, lut = 0, time.time(), time.time()
                    while sent < fs:
                        data = f.read(self.buffer_size);
                        conn.sendall(data);
                        sent += len(data);
                        self.update_progress(int(sent / fs * 100))
                        ct = time.time()
                        if ct - lut > 0.25:
                            et = ct - st;
                            spd = sent / et if et > 0 else 0;
                            eta = (fs - sent) / spd if spd > 0 else 0
                            wx.CallAfter(self.SetStatusText,
                                         f"Uploading at {self.format_speed(spd)} | ETA: {self.format_eta(eta)}")
                            lut = ct
                if conn.recv(2) == b"OK":
                    self.log_client(f"Upload successful: {fn}", 'success'); wx.CallAfter(self.SetStatusText,
                                                                                         "Upload complete.")
                else:
                    self.log_client(f"Upload failed for {fn}.", 'error'); wx.CallAfter(self.SetStatusText,
                                                                                       "Upload failed.")
        except Exception as e:
            self.log_client(f"Upload error: {e}", 'error'); wx.CallAfter(self.SetStatusText, "Upload error.")
        finally:
            self.update_progress(0, False); wx.CallAfter(self.set_client_controls_enabled, True)

    def on_download_file(self, e):
        sel = self.remote_files.GetSelection()
        if sel == wx.NOT_FOUND: wx.MessageBox("Please select a file.", "No File Selected"); return
        threading.Thread(target=self.download_file_worker, args=(self.remote_files.GetString(sel),),
                         daemon=True).start()

    def download_file_worker(self, fn):
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
                conn.sendall(struct.pack('!I', len(fn)) + fn.encode('utf-8'))
                fs = struct.unpack('!Q', self.receive_exactly(conn, 8))[0]
                if fs == 0: self.log_client(f"File not found: {fn}", 'error'); wx.CallAfter(self.SetStatusText,
                                                                                            "File not found."); return
                fp = os.path.join(self.client_downloads_dir, fn)
                with open(fp, 'wb') as f:
                    rec, st, lut = 0, time.time(), time.time()
                    while rec < fs:
                        c = self.receive_exactly(conn, min(self.buffer_size, fs - rec));
                        f.write(c);
                        rec += len(c);
                        self.update_progress(int(rec / fs * 100))
                        ct = time.time()
                        if ct - lut > 0.25:
                            et = ct - st;
                            spd = rec / et if et > 0 else 0;
                            eta = (fs - rec) / spd if spd > 0 else 0
                            wx.CallAfter(self.SetStatusText,
                                         f"Downloading at {self.format_speed(spd)} | ETA: {self.format_eta(eta)}");
                            lut = ct
                self.log_client(f"Download successful: {fn}", 'success');
                wx.CallAfter(self.SetStatusText, "Download complete.")
        except Exception as e:
            self.log_client(f"Download error: {e}", 'error'); wx.CallAfter(self.SetStatusText, "Download error.")
        finally:
            self.update_progress(0, False); wx.CallAfter(self.set_client_controls_enabled, True)

    def on_close(self, e):
        self.save_config(); self.Destroy()


if __name__ == '__main__':
    app = wx.App(False)
    frame = FileTransferApp()
    frame.Show()
    app.MainLoop()