import queue
import flet as ft
import base64
import cv2
import threading
import time
import components.tcpserver as tcpserver
import os
import inspect


def build(page: ft.Page, shared: dict) -> ft.Control:
    REQUIRED_CODE = "1234"
    # create or reuse camera_frame and register in shared
    if "camera_frame" in shared:
        camera_frame = shared["camera_frame"]
    else:
        camera_img = ft.Image(
            src=(
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
            ),
            width=640,
            height=480,
            fit=ft.ImageFit.CONTAIN,
            border_radius=ft.border_radius.all(8),
        )

        camera_frame = ft.Container(
            content=camera_img,
            width=640*1.3,
            height=480*1.3,
            padding=8,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            border_radius=ft.border_radius.all(10),
            alignment=ft.alignment.center,
        )
        shared["camera_frame"] = camera_frame

    # local camera state for this page
    state = {
        "running": False,
        "thread": None,
        "capture": None,
        # --- grid state ---
        "rows": 5,   # เริ่มต้น 8 แถว
        "cols": 8,   # เริ่มต้น 6 คอลัมน์
        "cell_size": 65,  # ขนาดพิกเซลของการ์ด (กว้าง/สูง)
        "layer_size": 3,  # จำนวนชั้น (floor)
        # --- tcp / processing ---
        "server_running": False,
        "processing": False,
        "processing_thread": None,
        "last_frame": None,
        "tcp_host": "127.0.0.1",          # <-- added
        "tcp_port": 5001,               # <-- added
        "tcp_server": None,
        "message_queue": None,
        "counter": 0,
        
    }

    # Single authoritative result text
    result_output = ft.Text("No result yet.", size=14)

    def ui_set_result(msg: str):
        def _():
            result_output.value = msg
            result_output.update()
        try:
            page.invoke_later(_)
        except Exception:
            _()

    # --------- เพิ่ม: ระบบ log พื้นหลังสำหรับ result_output ----------
    # สร้างคิวและเธรดอัปเดตข้อความ (ทำครั้งแรกเท่านั้น)
    if "ui_log_initialized" not in shared:
        shared["ui_log_initialized"] = True
        shared["_ui_log_queue"] = queue.Queue()
        shared["_ui_log_running"] = True

        def _ui_log_worker():
            while shared.get("_ui_log_running"):
                try:
                    msg = shared["_ui_log_queue"].get(timeout=0.5)
                except queue.Empty:
                    continue
                ui_set_result(msg)

        threading.Thread(target=_ui_log_worker, daemon=True, name="UIResultLogWorker").start()

        def ui_log(message: str):
            """ส่งข้อความหนึ่งบรรทัดไปแสดงที่ RESULT (ทับข้อความก่อนหน้า)"""
            q = shared.get("_ui_log_queue")
            if q:
                q.put(message)

        # ปรับ print ให้ส่งเข้า UI ด้วย (ยังคงโชว์ใน console)
        _orig_print = print
        def ui_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            ui_log(msg)
            _orig_print(*args, **kwargs)

        shared["ui_log"] = ui_log       # ใช้ส่งข้อความเดี่ยว
        shared["ui_print"] = ui_print   # ใช้เหมือน print()

    # helper ภายในไฟล์นี้ (เขียนสั้น)
    def log(msg: str):
        shared["ui_log"](msg)

    # ----------- TCP / SERVER LOGIC -------------
    def _message_reader(q: queue.Queue):
        while state["server_running"]:
            try:
                msg = q.get(timeout=0.4)
            except queue.Empty:
                continue
            # เดิม: ui_set_result(f"MSG: {msg}")
            log(f"MSG: {msg}")

    def start_tcp_server():
        if state["server_running"]:
            return
        try:
            threading.Thread(
                target=_run_tcp_server_wrapper,
                daemon=True,
                name="TCPServerThread"
            ).start()
            state["server_running"] = True
            log(f"Starting TCP server {state['tcp_host']}:{state['tcp_port']} ...")
        except Exception as ex:
            state["server_running"] = False
            log(f"Start server error: {ex}")

    def _run_tcp_server_wrapper():
        try:
            fn = getattr(tcpserver, "start_tcp_server")
            sig = inspect.signature(fn)
            print(f"[tcp] start_tcp_server signature: {sig}")
            server_obj = None

            params = set(sig.parameters.keys())
            if {"host", "port", "message_queue"} <= params:
                q = queue.Queue()
                state["message_queue"] = q
                server_obj = tcpserver.start_tcp_server(host=state["tcp_host"], port=state["tcp_port"], message_queue=q)
                threading.Thread(target=_message_reader, args=(q,), daemon=True, name="TCPMessageReader").start()
            elif {"host", "port"} <= params:
                server_obj = fn(host=state["tcp_host"], port=state["tcp_port"])
            elif len(sig.parameters) == 2:
                # assume positional (host, port)
                server_obj = fn(state["tcp_host"], state["tcp_port"])
            else:
                # fallback no-arg
                server_obj = fn()
            state["tcp_server"] = server_obj
            ui_set_result(f"TCP Server running on {state['tcp_host']}:{state['tcp_port']}")
        except Exception as ex:
            ui_set_result(f"Server error: {ex}")
            state["server_running"] = False

    def stop_tcp_server():
        if not state["server_running"]:
            return
        try:
            if hasattr(tcpserver, "stop_server"):
                try:
                    tcpserver.stop_server()
                except Exception as e:
                    print("stop_server() error:", e)
            srv = state.get("tcp_server")
            if srv:
                for m in ("stop", "close", "shutdown"):
                    if hasattr(srv, m):
                        try:
                            getattr(srv, m)()
                        except Exception:
                            pass
        finally:
            pass
            state["server_running"] = False
            state["tcp_server"] = None
            state["message_queue"] = None
            ui_set_result("SERVER STOPPED.")
            log("SERVER STOPPED.")

    # ------------- PROCESSING LOGIC ---------------
    def processing_start():
        if state["processing"]:
            return
        state["processing"] = True
        log("Processing started...")

        def _consume_message():
            if not state["processing"]:
                return
            q = state.get("message_queue")
            if not q:
                # ยังไม่มีคิว -> รอแล้วลองใหม่
                threading.Timer(0.2, _consume_message).start()
                return
            try:
                msg = q.get(timeout=0.5)
            except queue.Empty:
                # ไม่มีข้อความตอนนี้ -> ลองใหม่
                threading.Timer(0.1, _consume_message).start()
                return
            if msg is None:
                # ข้าม (sentinel) แล้วฟังต่อ
                threading.Timer(0.01, _consume_message).start()
                return
            
            text = str(msg).strip()
            if text == "Capture:1":
                log("done capture1")
            elif text == "finnish":
                log("finnished")
                increment_counter()
            else:
                log(f"MSG: {text}")

            # ต่อรอบถัดไป
            threading.Timer(0.0, _consume_message).start()

        # เริ่มรอบแรกในเธรด
        threading.Timer(0.0, _consume_message).start()

    def processing_stop():
        if not state["processing"]:
            return
        state["processing"] = False
        # ใส่ None ปลด block (ถ้ามีใครรอ)
        q = state.get("message_queue")
        if q:
            try:
                q.put_nowait(None)
            except Exception:
                pass
        log("Processing stopped.")

    def toggle_server(e):
        btn: ft.Control = e.control
        if not state["server_running"]:
            start_tcp_server()
            processing_start()
            btn.text = "STOP"
            btn.icon = ft.Icons.STOP
            btn.style = ft.ButtonStyle(
                bgcolor=ft.Colors.RED,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=20,
            )
        else:
            stop_tcp_server()
            processing_stop()
            btn.text = "START"
            btn.icon = ft.Icons.PLAY_ARROW
            btn.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=20,
            )
        btn.update()

    def reset_process(e):
        result_output.value = "RESET. TCP Server stopped."
        result_output.update()

    def camera_worker(cam_index=0):
        try:
            cap = cv2.VideoCapture(cam_index)
            state["capture"] = cap
            if not cap or not cap.isOpened():
                ui_set_result(f"Camera {cam_index} not opened.")
                return
            while state["running"]:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue
                ok, im_arr = cv2.imencode('.png', frame)
                if not ok:
                    time.sleep(0.05)
                    continue
                im_b64 = base64.b64encode(im_arr.tobytes()).decode('utf-8')

                def update_img(b64=im_b64):
                    if hasattr(camera_frame.content, 'src_base64'):
                        camera_frame.content.src_base64 = b64
                    try:
                        page.update()
                    except Exception:
                        pass

                try:
                    page.invoke_later(update_img)
                except Exception:
                    update_img()

                time.sleep(0.03)
        finally:
            if state["capture"]:
                try:
                    state["capture"].release()
                except Exception:
                    pass
            state["capture"] = None
            state["running"] = False

    def start(cam_index=0):
        if state["running"]:
            return
        state["running"] = True
        state["thread"] = threading.Thread(target=camera_worker, args=(cam_index,), daemon=True)
        state["thread"].start()

    def stop():
        if not state["running"]:
            return
        state["running"] = False
        if state["thread"] is not None:
            state["thread"].join(timeout=1)
        # reset placeholder
        if hasattr(camera_frame.content, 'src'):
            camera_frame.content.src = (
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
            )

    # register start/stop into shared so app can call stop when switching views
    shared["start_camera"] = start
    shared["stop_camera"] = stop

    def toggle(e):
        if not state["running"]:
            
            connect_btn.text = "Disconnect Camera"
            connect_btn.icon = ft.Icons.VIDEOCAM_OFF
        else:
            
            connect_btn.text = "Connect Camera"
            connect_btn.icon = ft.Icons.VIDEOCAM
        connect_btn.update()

   

    # ---------- GRID (การ์ด 10x10) ด้านขวา ----------
    grid_container = ft.Column(spacing=2)

    pixel_count_text = ft.Text(size=20, color=ft.Colors.BLUE_GREY)

    # Spacing constants used in width calculation
    COL_SPACING = 2  # spacing between cells horizontally
    OUTER_PADDING = 10  # right_panel padding
    INNER_PADDING = 6  # padding of inner container wrapping grid

    def compute_panel_width():
        size = state["cell_size"]
        cols = state["cols"]
        floor = state["layer_size"]
        if cols < 1:
            return 300
        grid_width = cols * size + (cols - 1) * COL_SPACING
        total = (OUTER_PADDING * 2) + (INNER_PADDING * 2) + grid_width
        # ensure control row (inputs) has some space
        return max(320, total)

    def build_grid(do_update: bool = False):
        # Rebuild grid cells; avoid calling update() before this control
        # is actually attached to the page to prevent AssertionError.
        rows_ui = []
        for r in range(state["rows"]):
            row_cells = []
            for c in range(state["cols"]):
                size = state["cell_size"]
                row_cells.append(
                    ft.Container(
                        width=size,
                        height=size,
                        bgcolor=ft.Colors.BLUE_400,
                        border_radius=2,
                        tooltip=f"({r},{c}) px",
                    )
                )
            rows_ui.append(ft.Row(row_cells, spacing=2))
        grid_container.controls = rows_ui
        pixel_count_text.value = (
            f"{state['rows']} x {state['cols']} x {state['layer_size']} = {state['rows'] * state['cols'] * state['layer_size']} Box"
        )
        if do_update:
            grid_container.update()
            pixel_count_text.update()

    tf_rows = ft.TextField(
        value=str(state["rows"]),
        label="แถว",
        width=80,
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )
    tf_cols = ft.TextField(
        value=str(state["cols"]),
        label="คอลัมน์",
        width=95,
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )

    layer_pallet = ft.TextField(
        value=str(state["layer_size"]),
        label="floor",
        width=80,
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )

    tf_size = ft.TextField(
        value=str(state["cell_size"]),
        label="Pixel",
        width=80,
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )

    def apply_grid(e):
        try:
            r = max(1, min(200, int(tf_rows.value)))
            c = max(1, min(200, int(tf_cols.value)))
            s = max(2, min(100, int(tf_size.value)))
            f = max(1, min(500, int(layer_pallet.value)))   # เพิ่ม: อ่าน floor
            state["rows"] = r
            state["cols"] = c
            state["cell_size"] = s
            state["layer_size"] = f                        # เพิ่ม: อัปเดต floor
            build_grid(do_update=True)                     # จะอัปเดต pixel_count_text ภายใน
            right_panel.width = compute_panel_width()
            right_panel.update()
            if 'bottom_controls' in locals():
                bottom_controls.width = right_panel.width
                bottom_controls.update()
        except ValueError:
            pass

    # ------- Password (Code) Dialog before applying grid --------
      # เปลี่ยนรหัสได้ตามต้องการ

    code_input = ft.TextField(
        label="กรุณากรอกรหัส",
        password=True,
        can_reveal_password=True,
        autofocus=True,
        width=250,
    )
    code_error = ft.Text(value="", color=ft.Colors.RED_400, size=12)

    def confirm_code(e):
        if code_input.value.strip() == REQUIRED_CODE:
            password_dialog.open = False
            page.update()
            apply_grid(None)
            page.snack_bar = ft.SnackBar(ft.Text("ปรับค่ากริดเรียบร้อย"), open=True)
            page.update()
        else:
            code_error.value = "รหัสไม่ถูกต้อง"
            code_error.update()

    def cancel_code(e):
        password_dialog.open = False
        page.update()

    password_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("ยืนยันรหัส"),
        content=ft.Column(
            [code_input, code_error],
            tight=True,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        actions=[
            ft.TextButton("CANCEL", on_click=cancel_code),
            ft.FilledButton("OK", on_click=confirm_code),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def open_code_dialog(e):
        print("DEBUG: apply_btn clicked -> open_code_dialog()")  # ดูใน console
        code_input.value = ""
        code_error.value = ""
        # วิธีใหม่ (บางเวอร์ชันของ Flet)
        try:
            page.open(password_dialog)   # ถ้าใช้ได้จะเปิดทันที
            return
        except Exception:
            pass
        # วิธีเดิม (กำหนด page.dialog แล้วเปิด)
        page.dialog = password_dialog
        password_dialog.open = True
        page.update()

    apply_btn = ft.IconButton(
        icon=ft.Icons.RESTART_ALT,
        on_click=open_code_dialog,   # เปลี่ยนให้เปิด dialog
        tooltip="ปรับ",
        style=ft.ButtonStyle(padding=8),
    )

    # Initial build without updating (control not yet added to page tree)
    build_grid(do_update=False)

    right_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("COMPRESSOR PALLET SIZE", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([tf_rows, tf_cols, tf_size, layer_pallet, apply_btn], spacing=6, alignment=ft.MainAxisAlignment.START),
                pixel_count_text,
                ft.Container(
                    content=grid_container,
                    padding=6,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                    border_radius=8,
                ),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.START,

        ),
        padding=10,
        margin=ft.margin.all(0),
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
        border_radius=10,
        height=480*1.3,
        width=640,  # placeholder, set below
    )

    # Set initial dynamic width based on initial grid
    right_panel.width = compute_panel_width()

    # Header right counter (separate from result_output)
    counter_text = ft.Text("COUNTER : 0", size=38, weight=ft.FontWeight.BOLD)

    def increment_counter():
        state["counter"] += 1
        def _():
            counter_text.value = f"COUNTER : {state['counter']}"
            counter_text.update()
        try:
            page.invoke_later(_)
        except Exception:
            _()

    header_card_R = ft.Container(
        content=ft.Column(
            [
                counter_text,
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=right_panel.width,  # will be adjusted later if needed
        height=80,
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
        alignment=ft.alignment.center,
    )

    # ---------- RESULT CARD (ด้านซ้าย) ----------
    header_card_L = ft.Container(
        content=ft.Column(
            [
                ft.Text("ROBOT VISION", size=38, weight=ft.FontWeight.BOLD),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=640*1.3,  # ปรับให้กว้างเท่ากับกล้อง
        height=80,
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
        alignment=ft.alignment.center,
    )
    result_output = ft.Text("No result yet.", size=14)
    result_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("RESULT", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                result_output,
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        width=640*1.3,  # ปรับให้กว้างเท่ากับกล้อง
        height=140,
        padding=12,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
    )

    # ---------- CONTROL BUTTONS (ด้านล่างขวา) ----------
    def start_process(e):
        log("STARTED processing...")
    def reset_process(e):
        log("RESET.")

    connect_btn = ft.ElevatedButton(
        "CONNECT",
        icon=ft.Icons.VIDEOCAM,
        on_click=toggle,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=20),
        height=50,
        width=150,
    )

    start_btn = ft.FilledButton(
        "START",
        icon=ft.Icons.PLAY_ARROW,
        on_click=toggle_server,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=20),
        height=50,
        width=150,
    )

    reset_btn = ft.OutlinedButton(
        "RESET",
        icon=ft.Icons.RESTART_ALT,
        on_click=reset_process,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=20),
        height=50,
        width=150,
    )

    bottom_controls = ft.Container(
        content=ft.Column(
            [
                ft.Text("CONTROLS", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Row([connect_btn,start_btn, reset_btn], spacing=16, alignment=ft.MainAxisAlignment.CENTER),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        width=right_panel.width,  # ปรับให้กว้างเท่ากับการ์ดด้านบน (right_panel)
        height=140,               # ถ้าต้องการให้สูงเท่า ด้านบน: ใช้ height=right_panel.height
        padding=12,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
    )

    # ---------- BOTTOM ROW (Result + Controls) ----------
    # bottom_row = ft.Row(
    #     [
    #         result_card,
    #         bottom_controls,
    #     ],
    #     spacing=40,
    #     alignment=ft.MainAxisAlignment.CENTER,
    #     vertical_alignment=ft.CrossAxisAlignment.START,
    # )

    # สร้างเลย์เอาต์ใหม่: ซ้าย (กล้อง + ผลลัพธ์) / ขวา (กริด + ปุ่ม)
    main_layout = ft.Row(
        [
            ft.Column(
                [header_card_L,camera_frame, result_card],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Column(
                [header_card_R,right_panel, bottom_controls],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        ],
        spacing=40,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    return ft.Column(
        [
            # ft.Text("ROBOT VISION", size=40, weight="bold"),
            main_layout,
        ],
        spacing=5,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


# main moved to app.py; this module only provides build()
