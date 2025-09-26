import configparser
import pathlib
from typing import Dict, Tuple
import os
import tempfile

import flet as ft


def _config_path() -> pathlib.Path:
    # config.ini is located next to this file in the pages folder
    return pathlib.Path(__file__).parent / "config.ini"


def build(page: ft.Page, shared: dict) -> ft.Control:
    """Build the settings UI.

    - Loads values from `config.ini` in the same folder.
    - Renders an Expander per section, with a TextField per key.
    - Numeric-looking values are validated as numbers before saving.
    - Save writes back to the same file.

    Assumptions:
    - If a section appears multiple times in the file, the parser will keep the last occurrence (configparser behavior).
    """

    cfg = configparser.ConfigParser()
    cfg_path = _config_path()
    try:
        cfg.read(cfg_path, encoding="utf-8")
    except Exception as e:
        page.snack_bar = ft.SnackBar(ft.Text(f"Failed reading config: {e}"))
        page.snack_bar.open = True

    # Keep references to TextFields and metadata: (is_numeric)
    fields: Dict[Tuple[str, str], Tuple[ft.TextField, bool]] = {}

    sections_controls = []

    # Schema: target section -> list of (target_key, list of candidate (src_section, src_key), is_numeric)
    SCHEMA = {
        "PROGRAMS": [
            ("SCORE1", [("CAMERA", "SCORE1"), ("PLACE", "SCORE1")], True),
            ("SCORE2", [("CAMERA", "SCORE2"), ("PLACE", "SCORE2")], True),
            ("large_roi_height", [("CAMERA", "large_roi_height")], True),
            ("large_roi_width", [("CAMERA", "large_roi_width")], True),
            ("small_roi_height", [("CAMERA", "small_roi_height")], True),
            ("small_roi_width", [("CAMERA", "small_roi_width")], True),
            ("small_roi_begin", [("CAMERA", "small_roi_begin")], True),
            ("IMG_ERROR1", [("CAMERA", "IMG_ERROR1")], True),
            ("IMG_ERROR2", [("CAMERA", "IMG_ERROR2")], True),
        ],
        "ROBOT": [
            ("ROBOT_IP", [("ROBOT", "IP"), ("ROBOT", "ROBOT_IP")], False),
            ("offsetPickX", [("ROBOT", "offsetPickX")], True),
            ("offsetPickY", [("ROBOT", "offsetPickY")], True),
            ("offsetPlaceX", [("ROBOT", "offsetPlaceX")], True),
            ("offsetPlaceY", [("ROBOT", "offsetPlaceY")], True),
            ("calpick", [("ROBOT", "calpick")], True),
            ("calplace", [("ROBOT", "calplace")], True),
            ("angle", [("ROBOT", "angle")], True),
        ],
        "HARDWARE": [
            ("CAMERA_NAME", [("HARDWARE", "CAMERA_NAME")], False),
            ("CAMERA_IP", [("HARDWARE", "CAMERA_IP")], False),
            ("COMPUTER_IP", [("HARDWARE", "COMPUTER_IP")], False),
            ("EXPOSURE_TIME", [("HARDWARE", "exposure_time")], True),
            ("FRAMERATE", [("HARDWARE", "framerate")], True),
       ],
        "COMPRESSOR": [
            ("LINE", [("COMPRESSOR", "LINE")], False),
            ("MODEL", [("COMPRESSOR", "MODEL")], False),
            ("BATCH", [("COMPRESSOR", "BATCH")], False),
            ("ROW", [("COMPRESSOR", "ROW"), ("SIZE", "ROW")], True),
            ("COLUMN", [("COMPRESSOR", "COLUMN"), ("SIZE", "COLUMN")], True),
        ],
        "COUNTER": [
            ("NUM", [("COUNTER", "NUM")], True),
            ("CYCLE", [("COUNTER", "CYCLE")], True),
            ("TOTAL", [("COUNTER", "TOTAL")], True),
            ("SUM_C", [("COUNTER", "SUM_C")], True),
        ],
        
    }

    def _get_first(cfg_obj, candidates, default=""):
        for s, k in candidates:
            if cfg_obj.has_section(s) and cfg_obj.has_option(s, k):
                return cfg_obj.get(s, k)
        return default

    # Build controls following SCHEMA order and wrap each section in a Card
    section_cards = []
    for sec_name, keys in SCHEMA.items():
        rows = []
        for target_key, candidates, is_numeric in keys:
            val = _get_first(cfg, candidates, "")
            # smaller width for ROBOT fields to allow compact cards
            width = 200 
            tf = ft.TextField(value=val, label=target_key, width=width)
            fields[(sec_name, target_key)] = (tf, is_numeric)
            rows.append(ft.Row([tf], spacing=10))

        section_header = ft.Text(sec_name, weight="bold", size=14)
        section_col = ft.Column([section_header, ft.Column(rows, tight=True)], tight=True)
        # wrap section into a Card for visual separation
        card = ft.Card(ft.Container(section_col, padding=12), elevation=2)
        section_cards.append(card)

    # arrange section cards into a grid (keep card_width) and avoid one long column
    card_width = 250  # keep same card width

    # number of columns per row (change to 4 to get 4 cards in a single row if space allows)
    columns = 5

    # chunk section_cards into rows of `columns` items
    rows = [
        section_cards[i : i + columns] for i in range(0, len(section_cards), columns)
    ]

    row_controls = []
    for r in rows:
        # wrap each card in a Container to enforce width, then put them in a Row
        row_controls.append(
            ft.Row(
                [ft.Container(c, width=card_width, padding=0) for c in r],
                spacing=12,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )

    sections_controls = [
        ft.Container(
            ft.Column(
                row_controls,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                tight=False,
                expand=True,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=12,
            expand=True,
        )
    ]

    # feedback label
    feedback = ft.Text("")


    def _save(e=None):
        # validate numeric fields
        errors = []
        for (section, key), (tf, is_numeric) in fields.items():
            v = tf.value.strip()
            if is_numeric:
                if v == "":
                    errors.append(f"{section}.{key}: empty")
                    tf.error_text = "Required"
                    tf.update()
                    continue
                try:
                    float(v)
                    tf.error_text = None
                    tf.update()
                except Exception:
                    errors.append(f"{section}.{key}: not a number")
                    tf.error_text = "Must be number"
                    tf.update()

        if errors:
            page.snack_bar = ft.SnackBar(ft.Text("Errors: " + ", ".join(errors)))
            page.snack_bar.open = True
            page.update()
            return

        # write values back to config object
        for (section, key), (tf, _) in fields.items():
            if not cfg.has_section(section):
                cfg.add_section(section)
            cfg.set(section, key, tf.value.strip())

        # Atomic overwrite to the same config.ini that was read
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=str(cfg_path.parent),
                prefix=cfg_path.name + ".",
                suffix=".tmp",
            ) as tmp:
                cfg.write(tmp)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = pathlib.Path(tmp.name)

            os.replace(tmp_path, cfg_path)
            page.snack_bar = ft.SnackBar(ft.Text("Config saved"))
            page.snack_bar.open = True
            page.update()
        except Exception as exc:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            page.snack_bar = ft.SnackBar(ft.Text(f"Save failed: {exc}"))
            page.snack_bar.open = True
            page.update()


    def _reset(e=None):
        # reload from file
        cfg2 = configparser.ConfigParser()
        cfg2.read(cfg_path, encoding="utf-8")
        for (section, key), (tf, _) in fields.items():
            if cfg2.has_option(section, key):
                tf.value = cfg2.get(section, key)
            else:
                tf.value = ""
            tf.error_text = None
            tf.update()
        page.snack_bar = ft.SnackBar(ft.Text("Reloaded from file"))
        page.snack_bar.open = True
        page.update()


    save_btn = ft.ElevatedButton("Save", on_click=_save)
    reset_btn = ft.TextButton("Reset", on_click=_reset)

    controls = [ft.Text("Settings", size=18, weight="bold")]
    controls.extend(sections_controls)
    controls.append(ft.Row([save_btn, reset_btn], alignment=ft.MainAxisAlignment.START))
    controls.append(feedback)

    return ft.Container(ft.Column(controls, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.START))
