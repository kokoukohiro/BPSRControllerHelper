import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
import json
from typing import Optional
import brotli

# =========================
# キー値テーブル（アクション側 1 byte）
# =========================
KEY_OPTIONS = [
    (1,  "L方向入力"),
    (3,  "R方向入力"),
    (5,  "L2"),
    (6,  "R2"),
    (7,  "×"),
    (8,  "〇"),
    (10, "□"),
    (11, "△"),
    (13, "touchpad"),
    (14, "option"),
    (15, "share"),
    (17, "L1"),
    (18, "R1"),
    (19, "L3"),
    (20, "R3"),
    (23, "↑"),
    (24, "↓"),
    (25, "←"),
    (26, "→"),
]
VALUE_TO_LABEL = {value: label for value, label in KEY_OPTIONS}
LABEL_TO_VALUE = {label: value for value, label in KEY_OPTIONS}
BASE_ACTION_COMBO_VALUES = [label for _, label in KEY_OPTIONS]

ACTION_STATE_SINGLE = 0xFFFFFFFF
ACTION_STATE_HELPER1 = 0x00000000
ACTION_STATE_HELPER2 = 0x00000001

ACTION_HELPER_NONE_LABEL = "割り当てなし"
DETECTED_SAVE_MANUAL_LABEL = "設定ファイルを手動選択しました"
BUTTON_LAYOUT_FILE_NAME = "bpsr_controller_helper_config.json"

CONTROLLER_OPTIONS = ["PlayStation", "Nintendo", "Xbox"]
DEFAULT_CONTROLLER = "PlayStation"

CONTROLLER_DISPLAY_MAPS = {
    "PlayStation": {
        1: "L方向入力",
        3: "R方向入力",
        5: "L2",
        6: "R2",
        7: "×",
        8: "〇",
        10: "□",
        11: "△",
        13: "touchpad",
        14: "option",
        15: "share",
        17: "L1",
        18: "R1",
        19: "L3",
        20: "R3",
        23: "↑",
        24: "↓",
        25: "←",
        26: "→",
    },
    "Nintendo": {
        1: "L方向入力",
        3: "R方向入力",
        5: "ZL",
        6: "ZR",
        7: "B",
        8: "A",
        10: "Y",
        11: "X",
        13: "-",
        14: "+",
        15: "capture",
        17: "L",
        18: "R",
        19: "LS",
        20: "RS",
        23: "↑",
        24: "↓",
        25: "←",
        26: "→",
    },
    "Xbox": {
        1: "L方向入力",
        3: "R方向入力",
        5: "LT",
        6: "RT",
        7: "A",
        8: "B",
        10: "X",
        11: "Y",
        13: "view",
        14: "menu",
        15: "xbox",
        17: "LB",
        18: "RB",
        19: "LS",
        20: "RS",
        23: "↑",
        24: "↓",
        25: "←",
        26: "→",
    },
}


# =========================
# アンカー
# =========================
INPUT_ANCHOR = b"BKRInputConfigData"
PRESET_ANCHOR = b"BKL_SETID_7001"
PRESET_REL_OFFSET = 0x17
PRESET_DEFAULT_VALUE = 0x01
PRESET_UNAVAILABLE_TITLE = "確認/キャンセルは編集できません"
PRESET_UNAVAILABLE_MESSAGE = (
    "この設定ファイルでは、確認/キャンセル設定がゲーム内でまだ一度も編集されていないため、"
    "このツールでは確認/キャンセルを編集できません。\n"
    "ほかの項目はそのまま編集できます。"
)


# =========================
# 確認 / キャンセル プリセット
# コントローラごとに表示を切り替える
# =========================
PRESET_OPTIONS = {
    "PlayStation": [
        (0x01, "□ / ×"),
        (0x02, "× / 〇"),
        (0x03, "〇 / ×"),
    ],
    "Nintendo": [
        (0x01, "Y / B"),
        (0x02, "B / A"),
        (0x03, "A / B"),
    ],
    "Xbox": [
        (0x01, "X / A"),
        (0x02, "A / B"),
        (0x03, "B / A"),
    ],
}


# =========================
# 補助キー1 / 補助キー2 本体
# 4-byte little-endian
# =========================
HELPER_OPTIONS = [
    (0x01, "L1"),
    (0x02, "R1"),
    (0x04, "L2"),
    (0x08, "R2"),
]
HELPER_VALUE_TO_LABEL = {value: label for value, label in HELPER_OPTIONS}
HELPER_LABEL_TO_VALUE = {label: value for value, label in HELPER_OPTIONS}

HELPER_PETWHEEL_ANCHOR = b"PetWheel"
HELPER1_FROM_PETWHEEL_OFFSET = 0x1B
HELPER2_FROM_PETWHEEL_OFFSET = 0x1F

# 補助キー本体値 -> アクション側の 1byte 値
HELPER_MAIN_TO_ACTION_VALUE = {
    0x01: 17,  # L1
    0x02: 18,  # R1
    0x04: 5,   # L2
    0x08: 6,   # R2
}


# =========================
# 既知のアクション一覧
# 並び順はユーザー指定順
# =========================
ACTIONS = [
    {"name": "ジャンプ", "rel_offsets": [0x0133]},
    {"name": "ダッシュ/回避", "rel_offsets": [0x01C7]},
    {"name": "環境共鳴能力1", "rel_offsets": [0x0204]},
    {"name": "環境共鳴能力2", "rel_offsets": [0x0227]},
    {"name": "通常攻撃", "rel_offsets": [0x027E]},
    {"name": "特殊攻撃", "rel_offsets": [0x09E7]},
    {"name": "マスタリースキル1", "rel_offsets": [0x02D5]},
    {"name": "マスタリースキル2", "rel_offsets": [0x0312]},
    {"name": "マスタリースキル3", "rel_offsets": [0x034F]},
    {"name": "マスタリースキル4", "rel_offsets": [0x038C]},
    {"name": "究極スキル", "rel_offsets": [0x09AA]},
    {"name": "バトルイマジン1", "rel_offsets": [0x0A24]},
    {"name": "バトルイマジン2", "rel_offsets": [0x0A61]},
    {"name": "左でアイテム切り替え", "rel_offsets": [0x102D]},
    {"name": "アイテム使用", "rel_offsets": [0x03C9]},
    {"name": "右でアイテム切り替え", "rel_offsets": [0x106A]},
    {"name": "アクション", "rel_offsets": [0x0551, 0x158F]},
    {"name": "ロックオン/切り替え", "rel_offsets": [0x0406]},
    {"name": "エクストラスキル", "rel_offsets": [0x0A9E]},
    {"name": "インタラクト解除", "rel_offsets": [0x045D]},
    {"name": "クエスト追跡", "rel_offsets": [0x0514]},
    {"name": "UI非表示", "rel_offsets": [0x04D7]},
    {"name": "クエストアイテムのクイック使用", "rel_offsets": [0x049A]},
    {"name": "マップON/OFF", "rel_offsets": [0x0690]},
    {"name": "クエスト", "rel_offsets": [0x06CD]},
    {"name": "ソーシャルモード", "rel_offsets": [0x070A]},
    {"name": "メニューを開く", "rel_offsets": [0x084D]},
    {"name": "撮影", "rel_offsets": [0x076A]},
    {"name": "ダンジョン退出", "rel_offsets": [0x0810]},
    {"name": "アイテムを使用", "rel_offsets": [0x090D, 0x186B]},
    {"name": "クイック操作", "rel_offsets": [0x0BA4]},
    {"name": "乗り物召喚/解除", "rel_offsets": [0x0B44]},
    {"name": "招待承認", "rel_offsets": [0x0BE1]},
    {"name": "招待拒否", "rel_offsets": [0x0C1E]},
    {"name": "オートバトル", "rel_offsets": [0x0CBB]},
    {"name": "チャンネル", "rel_offsets": [0x0C7E]},
    {"name": "イラストガイド", "rel_offsets": [0x0CF8]},
    {"name": "クイックホイール", "rel_offsets": [0x0D35]},
    {"name": "クイックホイール切替（左）", "rel_offsets": [0x289C]},
    {"name": "クイックホイール切替（右）", "rel_offsets": [0x28B1]},
    {"name": "クイックホイール編集", "rel_offsets": [0x28EE]},
    {"name": "クエスト切り替え（左）", "rel_offsets": [0x0FB3]},
    {"name": "クエスト切り替え（右）", "rel_offsets": [0x0FD6]},
    {"name": "ズームアウト", "rel_offsets": [0x058E]},
    {"name": "ズームイン", "rel_offsets": [0x05A3]},
    {"name": "スキルパレットを開く", "rel_offsets": [0x1227, 0x1F7D]},
    {"name": "ロールスキル1", "rel_offsets": [0x1133]},
    {"name": "ロールスキル2", "rel_offsets": [0x1170]},
    {"name": "ロールスキル3", "rel_offsets": [0x11AD]},
    {"name": "ロールスキル4", "rel_offsets": [0x11EA]},
    {"name": "ホーム設計図", "rel_offsets": [0x124A]},
]

SPECIAL_ACTIONS_WITHOUT_HELPER = {
    "クイックホイール切替（左）",
    "クイックホイール切替（右）",
    "クイックホイール編集",
}

# =========================
# 入力レコード種別
# value の直前4バイトに入っている type
# =========================
INPUT_TYPE_KEYBOARD = 0x00000001
INPUT_TYPE_MOUSE = 0x00000002
INPUT_TYPE_CONTROLLER = 0x00000003

# =========================
# lodef / UU1 兼用補正
# ACTIONS はそのまま維持し、読み込み時に type で実offsetを判定する
#
# UU1では一部アクションで controller と keymouse の並びが入れ替わる。
# ここには「controller候補として見に行く追加offset」だけを置く。
# 実際に使うかどうかは type=0x00000003 + state構造で判定する。
# =========================
ACTION_CONTROLLER_OFFSET_ALIASES = {
    "環境共鳴能力2": [0x0241],
    "クエスト切り替え（右）": [0x0FF0],
    "ホーム設計図": [0x1264],
}


class SaveEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root

        def resource_path(*parts: str) -> Path:
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                base = Path(sys._MEIPASS)
            else:
                base = Path(__file__).resolve().parent
            return base.joinpath(*parts)

        # アプリアイコン
        icon_path = resource_path("assets", "icon.png")
        if icon_path.exists():
            self.app_icon = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self.app_icon)

        self.root.title("BPSR：パッド勢を救いたい")
        self.root.geometry("500x680")
        self.root.minsize(350, 50)

        self.file_path: Optional[Path] = None
        self.original_dec: Optional[bytes] = None

        self.input_anchor_pos: Optional[int] = None
        self.preset_anchor_pos: Optional[int] = None
        self.helper1_main_pos: Optional[int] = None
        self.helper2_main_pos: Optional[int] = None
        self._preset_supported = True

        self.combo_vars: dict[str, tk.StringVar] = {}
        self.comboboxes: dict[str, ttk.Combobox] = {}
        self.action_helper_vars: dict[str, tk.StringVar] = {}
        self.action_helper_combos: dict[str, ttk.Combobox] = {}


        self.path_var = tk.StringVar()
        self.detected_save_var = tk.StringVar()
        self.detected_saves: list[tuple[str, Path]] = []
        self.status_var = tk.StringVar(value="ファイル未選択")
        self.base_status_message = "ファイル未選択"

        self.preset_var = tk.StringVar()
        self.helper1_var = tk.StringVar()
        self.helper2_var = tk.StringVar()
        self.controller_var = tk.StringVar(value=DEFAULT_CONTROLLER)

        self.preset_combobox: Optional[ttk.Combobox] = None
        self.helper1_combobox: Optional[ttk.Combobox] = None
        self.helper2_combobox: Optional[ttk.Combobox] = None
        self.controller_combobox: Optional[ttk.Combobox] = None
        self.detected_save_combobox: Optional[ttk.Combobox] = None
        self.path_entry: Optional[ttk.Entry] = None
        self.rescan_button: Optional[ttk.Button] = None
        self.manual_select_button: Optional[ttk.Button] = None
        self.button_layout_save_button: Optional[ttk.Button] = None
        self.button_layout_load_button: Optional[ttk.Button] = None

        self.reset_button: Optional[ttk.Button] = None
        self.save_button: Optional[ttk.Button] = None

        self._suspend_events = False
        self._last_controller_type = self.controller_var.get()
        self._last_helper1_display = ""
        self._last_helper2_display = ""
        self._combobox_dropdown_open = False
        self._active_dropdown_combo: Optional[ttk.Combobox] = None
        self._dropdown_watch_job = None

        self._build_ui()
        self._bind_traces()
        self._bind_mousewheel()
        self._bind_clear_selection_click()
        self.rescan_detected_saves()
        self.update_save_button_state()

    def _get_program_dir(self) -> Path:
        """実行ファイルまたは.pyと同じフォルダを返す。"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    def get_button_layout_path(self) -> Path:
        return self._get_program_dir() / BUTTON_LAYOUT_FILE_NAME

    def _append_combo_value_if_missing(self, combo: Optional[ttk.Combobox], label: str):
        if combo is None or not label:
            return
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values

    def _collect_button_layout(self) -> dict:
        return {
            "version": 1,
            "controller": self.controller_var.get() or DEFAULT_CONTROLLER,
            "keybind": {
                "helper1": self.helper1_var.get(),
                "helper2": self.helper2_var.get(),
                "preset": self.preset_var.get(),
            },
            "actions": {
                action["name"]: {
                    "helper": self.action_helper_vars[action["name"]].get(),
                    "button": self.combo_vars[action["name"]].get(),
                }
                for action in ACTIONS
                if action["name"] in self.combo_vars
            },
        }

    def save_button_layout(self):
        """現在のUI上のボタン配置を、ゲーム設定とは別のJSONに保存する。"""
        try:
            path = self.get_button_layout_path()
            data = self._collect_button_layout()
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.base_status_message = f"ボタン配置を保存しました: {path.name}"
            self.update_save_button_state()
            messagebox.showinfo("配置保存", f"ボタン配置を保存しました。\n{path}")
        except Exception as ex:
            self.base_status_message = "ボタン配置の保存に失敗しました"
            self.update_save_button_state()
            messagebox.showerror("配置保存エラー", f"ボタン配置の保存に失敗しました。\n{ex}")

    def load_button_layout(self):
        """JSONからUI上のボタン配置だけを読み込む。localsave.bytesには書かない。"""
        path = self.get_button_layout_path()
        if not path.exists():
            messagebox.showerror("配置読み込みエラー", f"配置ファイルが見つかりません。\n{path}")
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("配置ファイルの形式が不正です。")

            controller = data.get("controller") or DEFAULT_CONTROLLER
            if controller not in CONTROLLER_OPTIONS:
                controller = DEFAULT_CONTROLLER

            keybind = data.get("keybind") or {}
            actions = data.get("actions") or {}
            if not isinstance(keybind, dict) or not isinstance(actions, dict):
                raise ValueError("配置ファイルの形式が不正です。")

            self._suspend_events = True
            try:
                self.controller_var.set(controller)
                self._last_controller_type = controller

                helper_value_to_label = self._get_helper_value_to_label()
                helper_values = [helper_value_to_label[value] for value, _ in HELPER_OPTIONS]
                if self.helper1_combobox is not None:
                    self.helper1_combobox["values"] = list(helper_values)
                if self.helper2_combobox is not None:
                    self.helper2_combobox["values"] = list(helper_values)

                preset_values = [label for _, label in self._get_current_preset_options()]
                if self.preset_combobox is not None:
                    self.preset_combobox["values"] = list(preset_values)

                helper1 = keybind.get("helper1")
                helper2 = keybind.get("helper2")
                preset = keybind.get("preset")

                if helper1 in helper_values:
                    self.helper1_var.set(helper1)
                if helper2 in helper_values:
                    self.helper2_var.set(helper2)
                if preset in preset_values:
                    self.preset_var.set(preset)

                self._refresh_action_helper_combobox_choices()
                self._refresh_action_combobox_choices()

                valid_action_labels = self._get_current_action_label_to_value()
                valid_helper_labels = set(self._get_action_helper_display_values())

                for action in ACTIONS:
                    name = action["name"]
                    saved = actions.get(name)
                    if not isinstance(saved, dict):
                        continue

                    helper_label = saved.get("helper")
                    if (
                        self._action_name_uses_helper_ui(name)
                        and helper_label in valid_helper_labels
                    ):
                        self.action_helper_vars[name].set(helper_label)

                    button_label = saved.get("button")
                    if button_label in valid_action_labels:
                        self._append_combo_value_if_missing(self.comboboxes.get(name), button_label)
                        self.combo_vars[name].set(button_label)

                self._refresh_action_combobox_choices()
                self._refresh_action_helper_combobox_choices()
                self._update_preset_editability()
            finally:
                self._suspend_events = False

            self.base_status_message = f"ボタン配置を読み込みました: {path.name}"
            self.update_save_button_state()
            messagebox.showinfo(
                "配置読み込み",
                "ボタン配置を読み込みました。\nゲーム設定へ反映するには、通常の保存ボタンを押してください。",
            )
        except Exception as ex:
            self.base_status_message = "ボタン配置の読み込みに失敗しました"
            self.update_save_button_state()
            messagebox.showerror("配置読み込みエラー", f"ボタン配置の読み込みに失敗しました。\n{ex}")

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        # スクロール全体
        self.canvas = tk.Canvas(main, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_canvas_yview)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = ttk.Frame(self.canvas, padding=10)
        self.content.columnconfigure(0, weight=1)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width)
        )

        row = 0

        # frame 1: ファイル選択
        file_group = ttk.LabelFrame(self.content, text="設定ファイルを選択", padding=8)
        file_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        file_group.columnconfigure(0, weight=1)
        row += 1

        # frame 2: 検出された設定ファイル
        detected_group = ttk.LabelFrame(self.content, text="検出された設定ファイル", padding=8)
        detected_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        detected_group.columnconfigure(0, weight=1)
        row += 1

        # frame 3: コントローラ種別
        controller_group = ttk.LabelFrame(self.content, text="コントローラを選択", padding=8)
        controller_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        controller_group.columnconfigure(0, weight=1)
        row += 1

        # frame 4: ボタン配置プリセット
        layout_group = ttk.LabelFrame(self.content, text="ボタン配置プリセット", padding=8)
        layout_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        layout_group.columnconfigure(0, weight=1)
        row += 1

        # frame 5: 補助キー + 確認/キャンセル
        keybind_group = ttk.LabelFrame(self.content, text="ボタン配置", padding=8)
        keybind_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        keybind_group.columnconfigure(0, weight=1)
        row += 1

        # frame 6: アクション一覧
        action_group = ttk.LabelFrame(self.content, text="ボタン配置", padding=8)
        action_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        action_group.columnconfigure(0, weight=1)
        row += 1

        # ファイル選択（最古版ベース、ボタン文言だけ変更）
        file_row = ttk.Frame(file_group)
        file_row.grid(row=0, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)

        self.path_entry = ttk.Entry(file_row, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.manual_select_button = ttk.Button(file_row, text="手動選択", command=self.select_file)
        self.manual_select_button.grid(row=0, column=1, sticky="e")

        ttk.Label(
            file_group,
            text=(
                "ボタン配置の設定ファイルは通常、次の場所にあります。\n"
                "%USERPROFILE%\\AppData\\LocalLow\\bokura\\[アジア版やSteam版などのフォルダ]\\ \n"
                "localsave\\Env1\\[数字のフォルダ]\\[キャラクターUIDのフォルダ]\\localsave.bytes (2 KB以上)"
            ),
            justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        # 検出された設定ファイル
        detected_row = ttk.Frame(detected_group)
        detected_row.grid(row=0, column=0, sticky="ew")
        detected_row.columnconfigure(0, weight=1)

        self.detected_save_combobox = ttk.Combobox(
            detected_row,
            textvariable=self.detected_save_var,
            state="readonly",
            justify="left",
        )
        self.detected_save_combobox.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.detected_save_combobox.bind("<<ComboboxSelected>>", self._on_detected_save_selected)
        self._register_combobox_bindings(self.detected_save_combobox)

        self.rescan_button = ttk.Button(detected_row, text="再スキャン", command=self.rescan_detected_saves)
        self.rescan_button.grid(row=0, column=1, sticky="e")

        # コントローラ種別（左テキストなし）
        controller_row = ttk.Frame(controller_group)
        controller_row.grid(row=0, column=0, sticky="ew", pady=(0, 0))
        controller_row.columnconfigure(0, weight=1)

        self.controller_combobox = ttk.Combobox(
            controller_row,
            textvariable=self.controller_var,
            values=CONTROLLER_OPTIONS,
            state="readonly",
            justify="left",
        )
        self.controller_combobox.grid(row=0, column=0, sticky="ew")
        self._register_combobox_bindings(self.controller_combobox)

        layout_row = ttk.Frame(layout_group)
        layout_row.grid(row=0, column=0, sticky="ew")
        layout_row.columnconfigure(0, weight=1)
        layout_row.columnconfigure(1, weight=1)

        self.button_layout_save_button = ttk.Button(
            layout_row,
            text="配置保存",
            command=self.save_button_layout,
        )
        self.button_layout_save_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.button_layout_load_button = ttk.Button(
            layout_row,
            text="配置読み込み",
            command=self.load_button_layout,
        )
        self.button_layout_load_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ttk.Label(
            layout_group,
            text=f"保存先: {BUTTON_LAYOUT_FILE_NAME}",
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        sub_row = 0

        helper_values = [
            self._get_helper_value_to_label()[value]
            for value, _ in HELPER_OPTIONS
        ]

        self.helper1_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="補助キー1",
            variable=self.helper1_var,
            values=list(helper_values),
            width=10,
        )
        sub_row += 1

        self.helper2_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="補助キー2",
            variable=self.helper2_var,
            values=list(helper_values),
            width=10,
        )
        sub_row += 1

        self.preset_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="確認/キャンセル",
            variable=self.preset_var,
            values=[label for _, label in self._get_current_preset_options()],
            width=10,
            pady=(0, 0),
        )

        action_row = 0
        for action in ACTIONS:
            self._add_action_row(action_group, action_row, action)
            action_row += 1

        # フッター（固定）
        footer = ttk.Frame(self.root, padding=(10, 6, 10, 10))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        button_frame = ttk.Frame(footer)
        button_frame.grid(row=0, column=1, sticky="e")

        self.save_button = ttk.Button(button_frame, text="保存", command=self.save_file, state="disabled")
        self.save_button.pack(side="right")

        self.reset_button = ttk.Button(button_frame, text="リセット", command=self.reset_values, state="disabled")
        self.reset_button.pack(side="right", padx=(0, 8))

        self.root.bind_class("TCombobox", "<MouseWheel>", self._on_combobox_mousewheel)

    def _register_combobox_bindings(self, combo: ttk.Combobox):
        if combo is None:
            return

        combo.configure(postcommand=lambda c=combo: self._on_combobox_dropdown_open(c))
        combo.bind("<<ComboboxSelected>>", self._on_combobox_dropdown_close, add="+")
        combo.bind("<Escape>", self._on_combobox_dropdown_close, add="+")
        combo.bind("<Return>", self._on_combobox_dropdown_close, add="+")
        combo.bind("<Tab>", self._on_combobox_dropdown_close, add="+")

    def _on_combobox_dropdown_open(self, combo: ttk.Combobox):
        self._active_dropdown_combo = combo
        self._combobox_dropdown_open = True
        self._start_dropdown_watch()

    def _start_dropdown_watch(self):
        if self._dropdown_watch_job is not None:
            return
        self._dropdown_watch_job = self.root.after(30, self._watch_active_dropdown)

    def _watch_active_dropdown(self):
        self._dropdown_watch_job = None

        combo = self._active_dropdown_combo
        if combo is None:
            self._combobox_dropdown_open = False
            return

        try:
            popdown = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
            is_mapped = self.root.tk.call("winfo", "ismapped", popdown) == 1
        except tk.TclError:
            is_mapped = False

        self._combobox_dropdown_open = bool(is_mapped)

        if is_mapped:
            self._dropdown_watch_job = self.root.after(30, self._watch_active_dropdown)
        else:
            self._active_dropdown_combo = None

    def _on_combobox_dropdown_close(self, event=None):
        self._combobox_dropdown_open = False
        self._active_dropdown_combo = None

        if self._dropdown_watch_job is not None:
            self.root.after_cancel(self._dropdown_watch_job)
            self._dropdown_watch_job = None
    
    def _on_combobox_focusout(self, combo: ttk.Combobox):
        # ドロップダウンリスト側へフォーカスが移るだけのことがあるので、
        # その場では閉じた扱いにせず、アイドル時に実際の表示状態を確認する
        self.root.after_idle(lambda c=combo: self._close_combobox_if_popdown_hidden(c))

    def _close_combobox_if_popdown_hidden(self, combo: ttk.Combobox):
        try:
            popdown = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
            is_mapped = self.root.tk.call("winfo", "ismapped", popdown)
            if is_mapped != 1:
                self._combobox_dropdown_open = False
        except tk.TclError:
            self._combobox_dropdown_open = False

    def _on_combobox_mousewheel(self, event):
        if self._combobox_dropdown_open:
            return "break"

        if not self._can_scroll_vertical():
            return "break"

        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_combobox_mousewheel_linux_up(self, event):
        if self._combobox_dropdown_open:
            return "break"

        if not self._can_scroll_vertical():
            return "break"

        self.canvas.yview_scroll(-1, "units")
        return "break"

    def _on_combobox_mousewheel_linux_down(self, event):
        if self._combobox_dropdown_open:
            return "break"

        if not self._can_scroll_vertical():
            return "break"

        self.canvas.yview_scroll(1, "units")
        return "break"

    def _add_top_combo_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        width: int = 9,
        pady=(0, 6),
    ) -> ttk.Combobox:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=pady)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")

        combo = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            state="readonly",
            width=width,
            justify="right",
        )
        combo.grid(row=0, column=1, sticky="e")
        self._register_combobox_bindings(combo)
        return combo

    def _add_action_row(self, parent: ttk.Frame, row: int, action: dict):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        frame.columnconfigure(0, weight=1)

        action_name = action["name"]
        uses_helper_ui = self._action_name_uses_helper_ui(action_name)

        ttk.Label(frame, text=action_name).grid(row=0, column=0, sticky="w")

        helper_var = tk.StringVar(value=ACTION_HELPER_NONE_LABEL)
        var = tk.StringVar()

        if uses_helper_ui:
            helper_combo = ttk.Combobox(
                frame,
                textvariable=helper_var,
                values=self._get_action_helper_display_values(),
                state="readonly",
                width=10,
                justify="right",
            )
            helper_combo.grid(row=0, column=1, sticky="e", padx=(8, 4))

            ttk.Label(frame, text="+").grid(row=0, column=2, sticky="e", padx=(0, 4))

            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=list(BASE_ACTION_COMBO_VALUES),
                state="readonly",
                width=10,
                justify="right",
            )
            combo.grid(row=0, column=3, sticky="e")

            self._register_combobox_bindings(helper_combo)
            self.action_helper_combos[action_name] = helper_combo
        else:
            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=list(BASE_ACTION_COMBO_VALUES),
                state="readonly",
                width=10,
                justify="right",
            )
            combo.grid(row=0, column=1, columnspan=3, sticky="e")

        self._register_combobox_bindings(combo)

        self.action_helper_vars[action_name] = helper_var
        self.combo_vars[action_name] = var
        self.comboboxes[action_name] = combo

    def _bind_traces(self):
        self.controller_var.trace_add("write", self._on_controller_changed)
        self.preset_var.trace_add("write", self._on_any_value_changed)
        self.helper1_var.trace_add("write", self._on_helper1_changed)
        self.helper2_var.trace_add("write", self._on_helper2_changed)

        for var in self.combo_vars.values():
            var.trace_add("write", self._on_any_value_changed)

    def _bind_mousewheel(self):
        def _on_mousewheel(event):
            # Combobox のドロップダウンが開いている間は、親画面をスクロールしない
            if self._combobox_dropdown_open:
                return "break"

            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

        def _on_mousewheel_linux_up(event):
            # Combobox のドロップダウンが開いている間は、親画面をスクロールしない
            if self._combobox_dropdown_open:
                return "break"

            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(-1, "units")
                return "break"

        def _on_mousewheel_linux_down(event):
            # Combobox のドロップダウンが開いている間は、親画面をスクロールしない
            if self._combobox_dropdown_open:
                return "break"

            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(1, "units")
                return "break"

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.canvas.bind_all("<Button-4>", _on_mousewheel_linux_up)
        self.canvas.bind_all("<Button-5>", _on_mousewheel_linux_down)
    
    def _bind_clear_selection_click(self):
        self.root.bind_all("<Button-1>", self._on_global_left_click, add="+")

    def _on_global_left_click(self, event):
        widget = event.widget

        # event.widget が文字列で来る場合があるので実ウィジェットへ変換
        if isinstance(widget, str):
            try:
                widget = self.root.nametowidget(widget)
            except (KeyError, tk.TclError):
                return

        if widget is None:
            return

        try:
            widget_class = widget.winfo_class()
        except tk.TclError:
            return

        # 入力系ウィジェットをクリックしたときは何もしない
        interactive_classes = {
            "Entry", "TEntry",
            "Text",
            "Listbox",
            "Spinbox",
            "Combobox", "TCombobox",
        }
        if widget_class in interactive_classes:
            return

        # 少し遅らせて、現在のクリック処理が終わってから選択解除
        self.root.after_idle(self._clear_all_widget_selection)

    def _clear_all_widget_selection(self):
        # Entry の選択解除
        if self.path_entry is not None and self.path_entry.winfo_exists():
            try:
                self.path_entry.selection_clear()
            except tk.TclError:
                pass

        # Combobox の青い選択解除
        combo_list = [
            self.detected_save_combobox,
            self.controller_combobox,
            self.helper1_combobox,
            self.helper2_combobox,
            self.preset_combobox,
            *self.action_helper_combos.values(),
            *self.comboboxes.values(),
        ]

        for combo in combo_list:
            if combo is None or not combo.winfo_exists():
                continue
            try:
                combo.selection_clear()
            except tk.TclError:
                pass

        # どこにもフォーカスが残らないように root へ戻す
        try:
            self.root.focus_set()
        except tk.TclError:
            pass

    def _is_any_combobox_dropdown_open(self) -> bool:
        return self._combobox_dropdown_open

    def find_anchor(self, dec: bytes, anchor: bytes) -> int:
        pos = dec.find(anchor)
        if pos < 0:
            raise ValueError("必須データが見つかりません。")
        return pos

    def get_input_offsets(self, action: dict, dec: Optional[bytes] = None) -> list[int]:
        """
        BKRInputConfigData 基準のアクションvalue位置を返す。

        通常は ACTIONS の rel_offsets をそのまま使う。
        ただし UU1 では一部だけ controller/keymouse の並びが入れ替わるため、
        ACTIONS は変更せず、追加候補を type 判定して controller 実位置を解決する。
        """
        if self.input_anchor_pos is None:
            raise ValueError("入力設定が読み込まれていません。")

        rel_candidates = list(action["rel_offsets"])
        for rel in ACTION_CONTROLLER_OFFSET_ALIASES.get(action["name"], []):
            if rel not in rel_candidates:
                rel_candidates.append(rel)

        abs_candidates = [self.input_anchor_pos + rel for rel in rel_candidates]

        if dec is None:
            return abs_candidates

        resolved = [
            off for off in abs_candidates
            if self._is_standard_action_record(dec, off)
        ]

        # 対応版でない/未知構造の場合は、従来offsetを返して従来動作に戻す
        if resolved:
            return resolved

        return [self.input_anchor_pos + rel for rel in action["rel_offsets"]]

    def _is_standard_action_record(self, dec: bytes, off: int) -> bool:
        """
        controller側の標準アクションレコードか判定する。

        構造:
          off - 0x04 = type
          off + 0x00 = value
          off + 0x04 = state
          off + 0x08 = third dword

        キーマウ側は off - 0x04 が 0x01/0x02 なので除外する。
        """
        if off < 4 or off + 12 > len(dec):
            return False

        input_type = int.from_bytes(dec[off - 4:off], "little")
        state_dword = int.from_bytes(dec[off + 4:off + 8], "little")
        third_dword = int.from_bytes(dec[off + 8:off + 12], "little")

        return (
            input_type == INPUT_TYPE_CONTROLLER
            and state_dword in (ACTION_STATE_SINGLE, ACTION_STATE_HELPER1, ACTION_STATE_HELPER2)
            and third_dword == 0
        )

    def get_writable_input_offsets(self, action: dict, dec: bytes) -> list[int]:
        writable: list[int] = []
        for off in self.get_input_offsets(action, dec):
            if self._is_standard_action_record(dec, off):
                writable.append(off)
        return writable

    def _action_name_uses_helper_ui(self, action_name: str) -> bool:
        return action_name not in SPECIAL_ACTIONS_WITHOUT_HELPER

    def _action_allows_blocked_values(self, action_name: str) -> bool:
        return action_name in SPECIAL_ACTIONS_WITHOUT_HELPER

    def _get_default_preset_label(self) -> str:
        preset_value_to_label = self._get_current_preset_value_to_label()
        return preset_value_to_label.get(PRESET_DEFAULT_VALUE, next(iter(preset_value_to_label.values())))

    def _update_preset_editability(self):
        if self.preset_combobox is None:
            return
        self.preset_combobox.configure(state="readonly" if self._preset_supported else "disabled")

    def _show_preset_unavailable_error(self):
        messagebox.showerror(PRESET_UNAVAILABLE_TITLE, PRESET_UNAVAILABLE_MESSAGE)

    def get_preset_offset(self) -> int:
        if self.preset_anchor_pos is None:
            raise ValueError("確認/キャンセル設定が読み込まれていません。")
        return self.preset_anchor_pos + PRESET_REL_OFFSET

    def _is_valid_helper_main_value(self, value: int) -> bool:
        return value in HELPER_VALUE_TO_LABEL

    def find_helper_main_offsets(self, dec: bytes) -> tuple[int, int]:
        petwheel_pos = dec.find(HELPER_PETWHEEL_ANCHOR)
        if petwheel_pos < 0:
            raise ValueError("補助キー設定が見つかりません。")

        helper1_off = petwheel_pos + HELPER1_FROM_PETWHEEL_OFFSET
        helper2_off = petwheel_pos + HELPER2_FROM_PETWHEEL_OFFSET

        if helper2_off + 4 > len(dec):
            raise ValueError("補助キー設定が見つかりません。")

        helper1_value = int.from_bytes(dec[helper1_off:helper1_off + 4], "little")
        helper2_value = int.from_bytes(dec[helper2_off:helper2_off + 4], "little")

        if not self._is_valid_helper_main_value(helper1_value):
            raise ValueError("補助キー1の保存位置を特定できません。")
        if not self._is_valid_helper_main_value(helper2_value):
            raise ValueError("補助キー2の保存位置を特定できません。")

        return helper1_off, helper2_off

    def get_helper1_main_offset(self) -> int:
        if self.helper1_main_pos is None:
            raise ValueError("補助キー1の保存位置を特定できません。")
        return self.helper1_main_pos

    def get_helper2_main_offset(self) -> int:
        if self.helper2_main_pos is None:
            raise ValueError("補助キー2の保存位置を特定できません。")
        return self.helper2_main_pos

    def _ensure_combo_has_value(self, action_name: str, value: int, label: str):
        combo = self.comboboxes[action_name]
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values

    def _ensure_preset_has_value(self, value: int, label: str):
        if self.preset_combobox is None:
            return
        current_values = list(self.preset_combobox["values"])
        if label not in current_values:
            current_values.append(label)
            self.preset_combobox["values"] = current_values

    def _ensure_helper_has_value(self, which: str, value: int, label: str):
        combo = self.helper1_combobox if which == "helper1" else self.helper2_combobox
        if combo is None:
            return
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values

    def _get_current_action_value_to_label(self) -> dict[int, str]:
        controller = self.controller_var.get() or DEFAULT_CONTROLLER
        return CONTROLLER_DISPLAY_MAPS.get(controller, CONTROLLER_DISPLAY_MAPS[DEFAULT_CONTROLLER])

    def _get_current_action_label_to_value(self) -> dict[str, int]:
        value_to_label = self._get_current_action_value_to_label()
        return {label: value for value, label in value_to_label.items()}

    def _get_current_preset_options(self) -> list[tuple[int, str]]:
        controller = self.controller_var.get() or DEFAULT_CONTROLLER
        return PRESET_OPTIONS.get(controller, PRESET_OPTIONS[DEFAULT_CONTROLLER])

    def _get_current_preset_value_to_label(self) -> dict[int, str]:
        return {value: label for value, label in self._get_current_preset_options()}

    def _get_current_preset_label_to_value(self) -> dict[str, int]:
        return {label: value for value, label in self._get_current_preset_options()}

    def _get_helper_value_to_label(self) -> dict[int, str]:
        action_map = self._get_current_action_value_to_label()
        return {
            0x01: action_map[17],
            0x02: action_map[18],
            0x04: action_map[5],
            0x08: action_map[6],
        }

    def _get_helper_label_to_value(self) -> dict[str, int]:
        helper_map = self._get_helper_value_to_label()
        return {label: value for value, label in helper_map.items()}

    def _get_action_helper_display_values(self) -> list[str]:
        values = [ACTION_HELPER_NONE_LABEL]
        helper1_label = self.helper1_var.get()
        helper2_label = self.helper2_var.get()
        if helper1_label:
            values.append(helper1_label)
        if helper2_label and helper2_label not in values:
            values.append(helper2_label)
        return values

    def _get_action_helper_display_to_state(self) -> dict[str, int]:
        mapping = {ACTION_HELPER_NONE_LABEL: ACTION_STATE_SINGLE}
        helper1_label = self.helper1_var.get()
        helper2_label = self.helper2_var.get()
        if helper1_label:
            mapping[helper1_label] = ACTION_STATE_HELPER1
        if helper2_label:
            mapping[helper2_label] = ACTION_STATE_HELPER2
        return mapping

    def _refresh_action_helper_combobox_choices(self, old_helper1_label: Optional[str] = None, old_helper2_label: Optional[str] = None):
        new_values = self._get_action_helper_display_values()
        new_helper1_label = self.helper1_var.get()
        new_helper2_label = self.helper2_var.get()

        for name, combo in self.action_helper_combos.items():
            current = self.action_helper_vars[name].get()

            if old_helper1_label is not None and current == old_helper1_label:
                current = new_helper1_label
            elif old_helper2_label is not None and current == old_helper2_label:
                current = new_helper2_label

            combo["values"] = list(new_values)
            if current not in new_values:
                current = ACTION_HELPER_NONE_LABEL
            self.action_helper_vars[name].set(current)

        self._last_helper1_display = new_helper1_label
        self._last_helper2_display = new_helper2_label

    def _get_blocked_action_values(self) -> set[int]:
        blocked = set()
        helper_label_to_value = self._get_helper_label_to_value()

        helper1_label = self.helper1_var.get()
        if helper1_label in helper_label_to_value:
            helper1_main_value = helper_label_to_value[helper1_label]
            action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper1_main_value)
            if action_value is not None:
                blocked.add(action_value)

        helper2_label = self.helper2_var.get()
        if helper2_label in helper_label_to_value:
            helper2_main_value = helper_label_to_value[helper2_label]
            action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper2_main_value)
            if action_value is not None:
                blocked.add(action_value)

        return blocked

    def _refresh_action_combobox_choices(self):
        blocked_values = self._get_blocked_action_values()
        value_to_label = self._get_current_action_value_to_label()

        all_labels = [
            value_to_label[value]
            for value, _ in KEY_OPTIONS
        ]
        blocked_filtered_labels = [
            value_to_label[value]
            for value, _ in KEY_OPTIONS
            if value not in blocked_values
        ]

        for name, combo in self.comboboxes.items():
            current = self.combo_vars[name].get()
            if self._action_allows_blocked_values(name):
                values = list(all_labels)
            else:
                values = list(blocked_filtered_labels)
            if current and current not in values:
                values.append(current)
            combo["values"] = values

    def _refresh_controller_dependent_labels(self):
        old_controller = self._last_controller_type
        new_controller = self.controller_var.get() or DEFAULT_CONTROLLER

        old_helper1_label = self.helper1_var.get()
        old_helper2_label = self.helper2_var.get()

        old_action_value_to_label = CONTROLLER_DISPLAY_MAPS.get(old_controller, CONTROLLER_DISPLAY_MAPS[DEFAULT_CONTROLLER])
        old_action_label_to_value = {label: value for value, label in old_action_value_to_label.items()}
        new_action_value_to_label = CONTROLLER_DISPLAY_MAPS.get(new_controller, CONTROLLER_DISPLAY_MAPS[DEFAULT_CONTROLLER])

        old_helper_value_to_label = {
            0x01: old_action_value_to_label[17],
            0x02: old_action_value_to_label[18],
            0x04: old_action_value_to_label[5],
            0x08: old_action_value_to_label[6],
        }
        old_helper_label_to_value = {label: value for value, label in old_helper_value_to_label.items()}
        new_helper_value_to_label = self._get_helper_value_to_label()

        old_preset_options = PRESET_OPTIONS.get(old_controller, PRESET_OPTIONS[DEFAULT_CONTROLLER])
        new_preset_options = PRESET_OPTIONS.get(new_controller, PRESET_OPTIONS[DEFAULT_CONTROLLER])
        old_preset_label_to_value = {label: value for value, label in old_preset_options}
        new_preset_value_to_label = {value: label for value, label in new_preset_options}

        current_preset = self.preset_var.get()
        if current_preset in old_preset_label_to_value:
            preset_value = old_preset_label_to_value[current_preset]
            self.preset_var.set(new_preset_value_to_label.get(preset_value, current_preset))

        for helper_var in (self.helper1_var, self.helper2_var):
            current = helper_var.get()
            if current in old_helper_label_to_value:
                helper_value = old_helper_label_to_value[current]
                helper_var.set(new_helper_value_to_label.get(helper_value, current))

        for var in self.combo_vars.values():
            current = var.get()
            if not current:
                continue
            if current in old_action_label_to_value:
                action_value = old_action_label_to_value[current]
                var.set(new_action_value_to_label.get(action_value, current))

        helper_values = [new_helper_value_to_label[v] for v, _ in HELPER_OPTIONS]

        if self.helper1_combobox is not None:
            self.helper1_combobox["values"] = list(helper_values)
        if self.helper2_combobox is not None:
            self.helper2_combobox["values"] = list(helper_values)

        if self.preset_combobox is not None:
            current = self.preset_var.get()
            values = [label for _, label in new_preset_options]
            if current and current not in values:
                values.append(current)
            self.preset_combobox["values"] = values

        self._refresh_action_combobox_choices()
        self._refresh_action_helper_combobox_choices(
            old_helper1_label=old_helper1_label,
            old_helper2_label=old_helper2_label,
        )
        if not self._preset_supported:
            self.preset_var.set(self._get_default_preset_label())
        self._update_preset_editability()
        self._last_controller_type = new_controller

    def _on_any_value_changed(self, *args):
        if self._suspend_events:
            return
        self.update_save_button_state()

    def _clear_conflicts_for_helper_value(self, helper_main_value: int, other_helper: str):
        action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper_main_value)
        if action_value is None:
            return

        action_label_to_value = self._get_current_action_label_to_value()
        helper_label_to_value = self._get_helper_label_to_value()

        for action_name, var in self.combo_vars.items():
            if self._action_allows_blocked_values(action_name):
                continue
            label = var.get()
            if not label:
                continue
            value = action_label_to_value.get(label)
            if value == action_value:
                var.set("")

        other_var = self.helper1_var if other_helper == "helper1" else self.helper2_var
        other_label = other_var.get()
        if other_label:
            other_value = helper_label_to_value.get(other_label)
            if other_value == helper_main_value:
                other_var.set("")

    def _on_controller_changed(self, *args):
        if self._suspend_events:
            return

        self._suspend_events = True
        try:
            self._refresh_controller_dependent_labels()
        finally:
            self._suspend_events = False

        self.update_save_button_state()

    def _on_helper1_changed(self, *args):
        if self._suspend_events:
            return

        old_helper1_label = self._last_helper1_display

        self._suspend_events = True
        try:
            label = self.helper1_var.get()
            if label:
                value = self._get_helper_label_to_value().get(label)
                if value is not None:
                    self._clear_conflicts_for_helper_value(value, other_helper="helper2")
            self._refresh_action_combobox_choices()
            self._refresh_action_helper_combobox_choices(
                old_helper1_label=old_helper1_label,
                old_helper2_label=None,
            )
        finally:
            self._suspend_events = False

        self.update_save_button_state()

    def _on_helper2_changed(self, *args):
        if self._suspend_events:
            return

        old_helper2_label = self._last_helper2_display

        self._suspend_events = True
        try:
            label = self.helper2_var.get()
            if label:
                value = self._get_helper_label_to_value().get(label)
                if value is not None:
                    self._clear_conflicts_for_helper_value(value, other_helper="helper1")
            self._refresh_action_combobox_choices()
            self._refresh_action_helper_combobox_choices(
                old_helper1_label=None,
                old_helper2_label=old_helper2_label,
            )
        finally:
            self._suspend_events = False

        self.update_save_button_state()

    def has_blank_required_fields(self) -> bool:
        if self.file_path is None:
            return True

        if not self.helper1_var.get():
            return True
        if not self.helper2_var.get():
            return True
        if not self.preset_var.get():
            return True

        for var in self.combo_vars.values():
            if not var.get():
                return True

        return False

    def update_status_message(self):
        if self.file_path is None:
            self.status_var.set(self.base_status_message)
            return

        if self.has_blank_required_fields():
            self.status_var.set("未設定の項目があります")
        else:
            self.status_var.set(self.base_status_message)

    def update_save_button_state(self):
        if self.file_path is None or self.has_blank_required_fields():
            if self.save_button is not None:
                self.save_button.config(state="disabled")
        else:
            if self.save_button is not None:
                self.save_button.config(state="normal")

        self.update_status_message()

    def select_file(self):
        default_dir = self._resolve_default_open_dir()

        dialog_kwargs = {
            "title": "設定ファイルを選択",
            "filetypes": [("Bytes files", "*.bytes")],
        }

        # デフォルトで localsave.bytes を選択状態にしたい
        # （注: initialfile は存在しなくても指定可能）
        if default_dir is not None:
            dialog_kwargs["initialdir"] = str(default_dir)
            dialog_kwargs["initialfile"] = "localsave.bytes"

        path = filedialog.askopenfilename(**dialog_kwargs)
        if not path:
            return

        self._load_file(
            Path(path),
            error_title="読み込みエラー",
            success_message="読み込み完了",
            sync_detected_selection=False,
            show_preset_unavailable_warning=True,
        )

    def _scan_save_files(self) -> list[tuple[str, Path]]:
        results: list[tuple[str, Path]] = []
        bokura_root = Path.home() / "AppData" / "LocalLow" / "bokura"

        if not bokura_root.is_dir():
            return results

        for version_dir in bokura_root.iterdir():
            if not version_dir.is_dir():
                continue

            env1_root = version_dir / "localsave" / "Env1"
            if not env1_root.is_dir():
                continue

            for level1_dir in env1_root.iterdir():
                if not level1_dir.is_dir():
                    continue

                uid_dirs = [p for p in level1_dir.iterdir() if p.is_dir()]
                if len(uid_dirs) != 1:
                    continue

                uid_dir = uid_dirs[0]
                save_file = uid_dir / "localsave.bytes"
                if not save_file.is_file():
                    continue

                try:
                    if save_file.stat().st_size < 2048:
                        continue
                except OSError:
                    continue

                label = f"{version_dir.name}-UID:{uid_dir.name}"
                results.append((label, save_file))

        results.sort(key=lambda item: item[0].lower())
        return results

    def rescan_detected_saves(self):
        current_label = self.detected_save_var.get()
        self.detected_saves = self._scan_save_files()

        if self.detected_save_combobox is not None:
            self.detected_save_combobox["values"] = [label for label, _ in self.detected_saves]

        if not self.detected_saves:
            self.detected_save_var.set("")
            self.base_status_message = "設定ファイルが見つかりません、手動選択してください"
            self.update_save_button_state()
            return

        selected_label = None
        if current_label and any(label == current_label for label, _ in self.detected_saves):
            selected_label = current_label
        elif self.file_path is not None:
            try:
                current_path = self.file_path.resolve()
            except OSError:
                current_path = self.file_path
            for label, path in self.detected_saves:
                try:
                    candidate_path = path.resolve()
                except OSError:
                    candidate_path = path
                if candidate_path == current_path:
                    selected_label = label
                    break

        if selected_label is None:
            selected_label = self.detected_saves[0][0]

        self.detected_save_var.set(selected_label)
        self._load_detected_save_by_label(
            selected_label,
            show_error=False,
            success_message=f"{len(self.detected_saves)}件の設定ファイルを検出、{selected_label}を選択中",
            show_preset_unavailable_warning=False,
        )

    def _on_detected_save_selected(self, event=None):
        selected_label = self.detected_save_var.get()
        if not selected_label or selected_label == DETECTED_SAVE_MANUAL_LABEL:
            return

        self._load_detected_save_by_label(
            selected_label,
            show_error=True,
            success_message=f"{selected_label}を読み込み完了",
            show_preset_unavailable_warning=True,
        )

    def _load_detected_save_by_label(
        self,
        label: str,
        show_error: bool,
        success_message: Optional[str] = None,
        show_preset_unavailable_warning: bool = False,
    ):
        for detected_label, path in self.detected_saves:
            if detected_label == label:
                error_title = "読み込みエラー" if show_error else None
                self._load_file(
                    path,
                    error_title=error_title,
                    success_message=success_message,
                    show_preset_unavailable_warning=show_preset_unavailable_warning,
                )
                return

    def _load_file(
        self,
        file_path: Path,
        error_title: Optional[str],
        success_message: Optional[str] = None,
        sync_detected_selection: bool = True,
        show_preset_unavailable_warning: bool = False,
    ):
        try:
            raw = file_path.read_bytes()
            dec = brotli.decompress(raw)

            self.input_anchor_pos = self.find_anchor(dec, INPUT_ANCHOR)
            self.helper1_main_pos, self.helper2_main_pos = self.find_helper_main_offsets(dec)
            preset_anchor_pos = dec.find(PRESET_ANCHOR)
            if preset_anchor_pos >= 0:
                self.preset_anchor_pos = preset_anchor_pos
                self._preset_supported = True
            else:
                self.preset_anchor_pos = None
                self._preset_supported = False

            for action in ACTIONS:
                for off in self.get_input_offsets(action):
                    if off >= len(dec):
                        raise ValueError("ファイルの形式が想定と異なります。")

            if self._preset_supported and self.get_preset_offset() >= len(dec):
                raise ValueError("ファイルの形式が想定と異なります。")

            for off in (self.get_helper1_main_offset(), self.get_helper2_main_offset()):
                if off + 3 >= len(dec):
                    raise ValueError("ファイルの形式が想定と異なります。")

            self.file_path = file_path
            self.original_dec = dec
            self.path_var.set(str(file_path))

            if sync_detected_selection:
                matching_label = self._find_detected_label_by_path(file_path)
                if matching_label is not None:
                    self.detected_save_var.set(matching_label)
                else:
                    self.detected_save_var.set(DETECTED_SAVE_MANUAL_LABEL)
            else:
                self.detected_save_var.set(DETECTED_SAVE_MANUAL_LABEL)

            self._suspend_events = True
            try:
                self._load_values_from_dec(dec)
                self._refresh_action_combobox_choices()
                self._refresh_action_helper_combobox_choices()
                self._update_preset_editability()
            finally:
                self._suspend_events = False

            if self.reset_button is not None:
                self.reset_button.config(state="normal")

            self.base_status_message = success_message or "読み込み完了"
            self.update_save_button_state()

            if not self._preset_supported and show_preset_unavailable_warning:
                self._show_preset_unavailable_error()

        except Exception:
            self.file_path = None
            self.original_dec = None
            self.path_var.set("")
            self.preset_anchor_pos = None
            self.helper1_main_pos = None
            self.helper2_main_pos = None
            self._preset_supported = True
            self._update_preset_editability()
            self.base_status_message = "読み込み失敗"
            self.update_save_button_state()
            if error_title:
                messagebox.showerror(
                    error_title,
                    "ファイルの読み込みに失敗しました。\n対応していないファイルか、データが破損している可能性があります。"
                )

    def _find_detected_label_by_path(self, file_path: Path) -> Optional[str]:
        try:
            target = file_path.resolve()
        except OSError:
            target = file_path

        for label, path in self.detected_saves:
            try:
                if path.resolve() == target:
                    return label
            except OSError:
                if path == target:
                    return label
        return None

    def _load_values_from_dec(self, dec: bytes):
        action_value_to_label = self._get_current_action_value_to_label()
        helper_value_to_label = self._get_helper_value_to_label()
        preset_value_to_label = self._get_current_preset_value_to_label()

        if self._preset_supported:
            preset_off = self.get_preset_offset()
            preset_value = dec[preset_off]
            preset_label = preset_value_to_label.get(preset_value)
            if preset_label is None:
                preset_label = "不明"
                self._ensure_preset_has_value(preset_value, preset_label)
        else:
            preset_label = self._get_default_preset_label()
        self.preset_var.set(preset_label)

        helper1_off = self.get_helper1_main_offset()
        helper1_value = int.from_bytes(dec[helper1_off:helper1_off + 4], "little")
        helper1_label = helper_value_to_label.get(helper1_value)
        if helper1_label is None:
            helper1_label = "不明"
            self._ensure_helper_has_value("helper1", helper1_value, helper1_label)
        self.helper1_var.set(helper1_label)

        helper2_off = self.get_helper2_main_offset()
        helper2_value = int.from_bytes(dec[helper2_off:helper2_off + 4], "little")
        helper2_label = helper_value_to_label.get(helper2_value)
        if helper2_label is None:
            helper2_label = "不明"
            self._ensure_helper_has_value("helper2", helper2_value, helper2_label)
        self.helper2_var.set(helper2_label)

        action_helper_values = self._get_action_helper_display_values()

        for action in ACTIONS:
            name = action["name"]
            offsets = self.get_input_offsets(action, dec)
            first_off = offsets[0]
            first_value = int.from_bytes(dec[first_off:first_off + 4], "little")
            state_dword = int.from_bytes(dec[first_off + 4:first_off + 8], "little")

            label = action_value_to_label.get(first_value)
            if label is None:
                label = "不明"
                self._ensure_combo_has_value(name, first_value, label)

            if not self._action_name_uses_helper_ui(name):
                helper_label = ACTION_HELPER_NONE_LABEL
            elif state_dword == ACTION_STATE_SINGLE:
                helper_label = ACTION_HELPER_NONE_LABEL
            elif state_dword == ACTION_STATE_HELPER1:
                helper_label = self.helper1_var.get()
            elif state_dword == ACTION_STATE_HELPER2:
                helper_label = self.helper2_var.get()
            else:
                helper_label = ACTION_HELPER_NONE_LABEL

            if helper_label not in action_helper_values:
                helper_label = ACTION_HELPER_NONE_LABEL

            self.action_helper_vars[name].set(helper_label)
            self.combo_vars[name].set(label)

    def reset_values(self):
        if self.original_dec is None:
            return

        self._suspend_events = True
        try:
            self._load_values_from_dec(self.original_dec)
            self._refresh_action_combobox_choices()
            self._update_preset_editability()
        finally:
            self._suspend_events = False

        self.base_status_message = "読み込み時の状態に戻しました"
        self.update_save_button_state()

    def save_file(self):
        if self.file_path is None or self.original_dec is None:
            return

        if self.has_blank_required_fields():
            self.update_save_button_state()
            return

        try:
            dec = bytearray(self.original_dec)

            if self._preset_supported:
                preset_label_to_value = self._get_current_preset_label_to_value()
                preset_label = self.preset_var.get()
                if preset_label not in preset_label_to_value:
                    raise ValueError("確認/キャンセルの値が不正です。")
                dec[self.get_preset_offset()] = preset_label_to_value[preset_label]

            helper_label_to_value = self._get_helper_label_to_value()
            action_label_to_value = self._get_current_action_label_to_value()
            action_helper_display_to_state = self._get_action_helper_display_to_state()

            helper1_label = self.helper1_var.get()
            if helper1_label not in helper_label_to_value:
                raise ValueError("補助キー1の値が不正です。")
            helper1_value = helper_label_to_value[helper1_label]
            helper1_off = self.get_helper1_main_offset()
            dec[helper1_off:helper1_off + 4] = helper1_value.to_bytes(4, "little")

            helper2_label = self.helper2_var.get()
            if helper2_label not in helper_label_to_value:
                raise ValueError("補助キー2の値が不正です。")
            helper2_value = helper_label_to_value[helper2_label]
            helper2_off = self.get_helper2_main_offset()
            dec[helper2_off:helper2_off + 4] = helper2_value.to_bytes(4, "little")

            for action in ACTIONS:
                name = action["name"]
                selected_label = self.combo_vars[name].get()
                if selected_label not in action_label_to_value:
                    raise ValueError(f"{name} の値が不正です。")

                if self._action_name_uses_helper_ui(name):
                    helper_display = self.action_helper_vars[name].get()
                    if helper_display not in action_helper_display_to_state:
                        raise ValueError(f"{name} の補助キー設定が不正です。")
                    state_dword = action_helper_display_to_state[helper_display]
                else:
                    state_dword = ACTION_STATE_SINGLE

                value = action_label_to_value[selected_label]

                for off in self.get_writable_input_offsets(action, self.original_dec):
                    dec[off:off + 4] = value.to_bytes(4, "little")
                    dec[off + 4:off + 8] = state_dword.to_bytes(4, "little")

            enc = brotli.compress(bytes(dec), quality=1)
            self.file_path.write_bytes(enc)

            self.original_dec = bytes(dec)

            self._suspend_events = True
            try:
                self._load_values_from_dec(self.original_dec)
                self._refresh_action_combobox_choices()
                self._refresh_action_helper_combobox_choices()
                self._update_preset_editability()
            finally:
                self._suspend_events = False

            self.base_status_message = "保存しました"
            self.update_save_button_state()
            messagebox.showinfo("保存完了", "保存しました。")

        except Exception:
            self.base_status_message = "保存失敗"
            self.update_save_button_state()
            messagebox.showerror(
                "保存エラー",
                "保存に失敗しました。入力内容を確認してください。"
            )

    def _can_scroll_vertical(self) -> bool:
        bbox = self.canvas.bbox("all")
        if not bbox:
            return False

        content_height = bbox[3] - bbox[1]
        view_height = self.canvas.winfo_height()

        return content_height > view_height + 1

    def _on_canvas_yview(self, first, last):
        self.scrollbar.set(first, last)

        first_f = float(first)
        last_f = float(last)

        # つまみが全長いっぱい = スクロール不要
        if first_f <= 0.0 and last_f >= 1.0:
            self.scrollbar.state(["disabled"])
        else:
            self.scrollbar.state(["!disabled"])

    def _pick_only_subdir(self, parent: Path) -> Optional[Path]:
        if not parent.is_dir():
            return None

        dirs = [p for p in parent.iterdir() if p.is_dir()]
        if len(dirs) == 1:
            return dirs[0]
        return None

    def _resolve_default_open_dir(self) -> Optional[Path]:
        """
        優先:
        %USERPROFILE%\\AppData\\LocalLow\\bokura\\[唯一のフォルダ]\\localsave\\Env1\\[唯一のフォルダ]\\[唯一のフォルダ]

        見つからなければ:
        %USERPROFILE%\\AppData\\LocalLow\\bokura

        それも無理なら:
        None
        """
        try:
            bokura_root = Path.home() / "AppData" / "LocalLow" / "bokura"

            # 優先パスをたどる
            level1 = self._pick_only_subdir(bokura_root)
            if level1 is not None:
                env1_root = level1 / "localsave" / "Env1"
                level2 = self._pick_only_subdir(env1_root)
                if level2 is not None:
                    level3 = self._pick_only_subdir(level2)
                    if level3 is not None and level3.is_dir():
                        return level3

            # 見つからなければ bokura 直下
            if bokura_root.is_dir():
                return bokura_root

            return None

        except Exception:
            return None


if __name__ == "__main__":
    root = tk.Tk()
    app = SaveEditorApp(root)
    root.mainloop()