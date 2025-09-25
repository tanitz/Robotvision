import flet as ft
from pages import home, setting, model, result


def main(page: ft.Page):
    page.title = "ROBOT VISION"

    page.theme_mode = ft.ThemeMode.LIGHT
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 20

    main_content = ft.Container()

    # shared object passed to page modules; home will create/register camera_frame
    shared = {}

    def switch_view(e, view_name):
        if view_name == "home":
            main_content.content = home.build(page, shared)
        if view_name == "setting":
            main_content.content = setting.build(page, shared)
        elif view_name == "model":
            main_content.content = model.build(page, shared)
        elif view_name == "result":
            main_content.content = result.build(page, shared)
        page.update()

    menu_bar = ft.Row(
        [
            ft.TextButton("Home", on_click=lambda e: switch_view(e, "home")),
            ft.TextButton("Setting", on_click=lambda e: switch_view(e, "setting")),
            ft.TextButton("Model", on_click=lambda e: switch_view(e, "model")),
            ft.TextButton("Result", on_click=lambda e: switch_view(e, "result")),
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=12,
    )

    switch_view(None, "home")

    page.add(
        ft.Column(
            [
                menu_bar,
                ft.Divider(height=1, thickness=1),
                main_content,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    page.window.maximized = True
    page.update()

    


if __name__ == '__main__':
    ft.app(target=main)
