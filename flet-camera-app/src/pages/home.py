import flet as ft
import base64
import cv2
import threading
import time


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
            width=640,
            height=480,
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
    }

    def camera_worker(cam_index=0):
        try:
            state["capture"] = cv2.VideoCapture(cam_index)
            if not state["capture"] or not state["capture"].isOpened():
                print(f"Error: Camera {cam_index} not opened.")
                return

            while state["running"]:
                ret, frame = state["capture"].read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

                ok, im_arr = cv2.imencode('.png', frame)
                if not ok:
                    time.sleep(0.05)
                    continue

                im_b64 = base64.b64encode(im_arr.tobytes()).decode('utf-8')
                # camera_frame contains an Image as content
                if hasattr(camera_frame.content, 'src_base64'):
                    camera_frame.content.src_base64 = im_b64
                try:
                    page.update()
                except Exception:
                    break

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
            start(0)
            connect_btn.text = "Disconnect Camera"
            connect_btn.icon = ft.Icons.VIDEOCAM_OFF
        else:
            stop()
            connect_btn.text = "Connect Camera"
            connect_btn.icon = ft.Icons.VIDEOCAM
        connect_btn.update()

    # btn = ft.ElevatedButton(
    #     "Open Camera",
    #     icon=ft.Icons.CAMERA_ALT_OUTLINED,
    #     on_click=toggle,
    #     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=15),
    # )

    # ---------- GRID (การ์ด 10x10) ด้านขวา ----------
    grid_container = ft.Column(spacing=2)

    pixel_count_text = ft.Text(size=12, color=ft.Colors.BLUE_GREY)

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
                ft.Text("COMPRESSOR PALLET SIZE", size=14, weight=ft.FontWeight.BOLD),
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
        height=480,
        width=0,  # placeholder, set below
    )

    # Set initial dynamic width based on initial grid
    right_panel.width = compute_panel_width()

    # ---------- LAYOUT รวม (กล้องซ้าย / กริดขวา) ----------
    camera_and_grid = ft.Row(
        [
            camera_frame,
            right_panel,
        ],
        spacing=40,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    # ---------- RESULT CARD (ด้านล่างซ้าย) ----------
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
        width=640,
        height=140,
        padding=12,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
    )

    # ---------- CONTROL BUTTONS (ด้านล่างขวา) ----------
    def start_process(e):
        result_output.value = "STARTED processing..."
        result_output.update()

    def reset_process(e):
        result_output.value = "RESET."
        # รีเซ็ต grid ค่าเดิม (ถ้าต้องการ)
        # state["rows"], state["cols"], state["cell_size"] = 5, 8, 65
        # build_grid(do_update=True)
        result_output.update()

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
        on_click=start_process,
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
    bottom_row = ft.Row(
        [
            result_card,
            bottom_controls,
        ],
        spacing=40,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    # สร้างเลย์เอาต์ใหม่: ซ้าย (กล้อง + ผลลัพธ์) / ขวา (กริด + ปุ่ม)
    main_layout = ft.Row(
        [
            ft.Column(
                [camera_frame, result_card],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Column(
                [right_panel, bottom_controls],
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
            ft.Text("ROBOT VISION", size=40, weight="bold"),
            main_layout,
        ],
        spacing=5,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


# main moved to app.py; this module only provides build()
