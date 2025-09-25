import flet as ft
import base64
import cv2
import threading
import time
import os
import datetime


def build(page: ft.Page, shared: dict) -> ft.Control:
    # state for camera thread in this page
    state = {
        "running": False,
        "thread": None,
        "capture": None,
        "last_frame": None,
    }

    # 1x1 transparent PNG placeholder (same as home.py)
    PLACEHOLDER_DATA_URL = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
        "AAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )

    # image card (same size as home.py)
    model_img = ft.Image(
        src=PLACEHOLDER_DATA_URL,
        width=640,
        height=480,
        fit=ft.ImageFit.CONTAIN,
        border_radius=ft.border_radius.all(8),
    )

    image_card = ft.Container(
        content=model_img,
        width=640,
        height=480,
        padding=8,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
        border_radius=ft.border_radius.all(10),
        alignment=ft.alignment.center,
    )

    def set_image_from_frame(frame):
        try:
            ok, im_arr = cv2.imencode(".png", frame)
            if not ok:
                return
            im_b64 = base64.b64encode(im_arr.tobytes()).decode("utf-8")
            if hasattr(image_card.content, "src_base64"):
                image_card.content.src_base64 = im_b64
            page.update()
        except Exception:
            pass

    def camera_worker(cam_index=0):
        try:
            state["capture"] = cv2.VideoCapture(cam_index)
            if not state["capture"] or not state["capture"].isOpened():
                page.snack_bar = ft.SnackBar(ft.Text(f"Cannot open camera {cam_index}"), open=True)
                page.update()
                state["running"] = False
                return

            while state["running"]:
                ret, frame = state["capture"].read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue
                state["last_frame"] = frame
                set_image_from_frame(frame)
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
        # reset to placeholder
        if hasattr(image_card.content, "src"):
            image_card.content.src = PLACEHOLDER_DATA_URL
        page.update()

    # expose stop so app can call it when switching views
    shared["model_stop_camera"] = stop

    # toolbar actions
    def on_connect(e):
        if not state["running"]:
            start(0)
            connect_btn.text = "Disconnect"
            connect_btn.icon = ft.Icons.VIDEOCAM_OFF
        else:
            stop()
            connect_btn.text = "Connect"
            connect_btn.icon = ft.Icons.VIDEOCAM
        connect_btn.update()

    def on_crop(e):
        frame = state["last_frame"]
        if frame is None:
            page.snack_bar = ft.SnackBar(ft.Text("No frame to crop."), open=True)
            page.update()
            return
        h, w = frame.shape[:2]
        size = min(h, w)
        x = (w - size) // 2
        y = (h - size) // 2
        crop = frame[y : y + size, x : x + size]
        state["last_frame"] = crop
        set_image_from_frame(crop)

    def on_capture(e):
        frame = state["last_frame"]
        if frame is None:
            page.snack_bar = ft.SnackBar(ft.Text("No frame to capture."), open=True)
            page.update()
            return
        # save to project_root/captures
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        out_dir = os.path.join(project_root, "captures")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"capture_{ts}.png")
        try:
            cv2.imwrite(out_path, frame)
            page.snack_bar = ft.SnackBar(ft.Text(f"Saved: {out_path}"), open=True)
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Save failed: {ex}"), open=True)
            page.update()

    def on_test(e):
        page.snack_bar = ft.SnackBar(ft.Text("Test clicked."), open=True)
        page.update()

    # toolbar (bottom)
    connect_btn = ft.ElevatedButton(
        "Connect",
        icon=ft.Icons.VIDEOCAM,
        on_click=on_connect,
        height=42,
        width=140,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=16),
    )
    crop_btn = ft.FilledButton(
        "Crop",
        icon=ft.Icons.CROP,
        on_click=on_crop,
        height=42,
        width=120,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=16),
    )
    capture_btn = ft.OutlinedButton(
        "Capture",
        icon=ft.Icons.CAMERA_ALT,
        on_click=on_capture,
        height=42,
        width=140,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=16),
    )
    test_btn = ft.OutlinedButton(
        "Test",
        icon=ft.Icons.PLAY_ARROW,
        on_click=on_test,
        height=42,
        width=120,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=16),
    )

    toolbar = ft.Container(
        content=ft.Row(
            [connect_btn, crop_btn, capture_btn, test_btn],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        width=640,
        padding=12,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=10,
    )

    return ft.Column(
        [
            ft.Text("Model", size=18, weight="bold"),
            image_card,
            toolbar,
        ],
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
