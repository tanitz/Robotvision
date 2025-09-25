import flet as ft


def build(page: ft.Page, shared: dict) -> ft.Control:
    return ft.Column(
        [
            ft.Text("Result", size=18, weight="bold"),
            ft.Text("Display results / logs here."),
        ],
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
