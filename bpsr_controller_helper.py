import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
from typing import Optional
import brotli

# =========================
# キー値テーブル（アクション側 1 byte）
# =========================
KEY_OPTIONS = [
    (5,  "L2"),
    (6,  "R2"),
    (7,  "×"),
    (8,  "〇"),
    (10, "□"),
    (11, "△"),
    (15, "select"),
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


# =========================
# アンカー
# =========================
INPUT_ANCHOR = b"BKRInputConfigData"
PRESET_ANCHOR = b"BKL_SETID_7001"
PRESET_REL_OFFSET = 0x17


# =========================
# 確認 / キャンセル プリセット
# =========================
PRESET_OPTIONS = [
    (0x01, "□ / ×"),
    (0x03, "〇 / ×"),
    (0x02, "× / 〇"),
]
PRESET_VALUE_TO_LABEL = {value: label for value, label in PRESET_OPTIONS}
PRESET_LABEL_TO_VALUE = {label: value for value, label in PRESET_OPTIONS}


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

HELPER1_MAIN_REL_OFFSET = 0x4B7D
HELPER2_MAIN_REL_OFFSET = 0x4B81

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
    {"name": "通常攻撃", "rel_offsets": [0x027E]},
    {"name": "特殊攻撃", "rel_offsets": [0x09E7]},
    {"name": "究極スキル", "rel_offsets": [0x09AA]},
    {"name": "左でアイテム切り替え", "rel_offsets": [0x102D]},
    {"name": "アイテム使用", "rel_offsets": [0x03C9]},
    {"name": "右でアイテム切り替え", "rel_offsets": [0x106A]},
    {"name": "アクション", "rel_offsets": [0x0551, 0x158F]},
    {"name": "ロックオン/切り替え", "rel_offsets": [0x0406]},
    {"name": "エクストラスキル", "rel_offsets": [0x0A9E]},
    {"name": "インタラクト解除", "rel_offsets": [0x045D]},
    {"name": "クエストアイテムのクイック使用", "rel_offsets": [0x049A]},
    {"name": "アイテムを使用", "rel_offsets": [0x090D, 0x186B]},
    {"name": "クイックホイール", "rel_offsets": [0x0D35]},
    {"name": "スキルパレットを開く", "rel_offsets": [0x1227, 0x1F7D]},
    {"name": "ロールスキル1", "rel_offsets": [0x1133]},
    {"name": "ロールスキル2", "rel_offsets": [0x1170]},
    {"name": "ロールスキル3", "rel_offsets": [0x11AD]},
    {"name": "ロールスキル4", "rel_offsets": [0x11EA]},
]


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

        self.combo_vars: dict[str, tk.StringVar] = {}
        self.comboboxes: dict[str, ttk.Combobox] = {}

        self.path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="ファイル未選択")
        self.base_status_message = "ファイル未選択"

        self.preset_var = tk.StringVar()
        self.helper1_var = tk.StringVar()
        self.helper2_var = tk.StringVar()

        self.preset_combobox: Optional[ttk.Combobox] = None
        self.helper1_combobox: Optional[ttk.Combobox] = None
        self.helper2_combobox: Optional[ttk.Combobox] = None
        self.path_entry: Optional[ttk.Entry] = None

        self.reset_button: Optional[ttk.Button] = None
        self.save_button: Optional[ttk.Button] = None

        self._suspend_events = False

        self._build_ui()
        self._bind_traces()
        self._bind_mousewheel()
        self.update_save_button_state()

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
        file_group = ttk.LabelFrame(self.content, text="ファイル選択", padding=8)
        file_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        file_group.columnconfigure(0, weight=1)
        row += 1

        # frame 2: 補助キー + 確認/キャンセル
        keybind_group = ttk.LabelFrame(self.content, text="ボタン配置", padding=8)
        keybind_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        keybind_group.columnconfigure(0, weight=1)
        row += 1

        # frame 3: アクション一覧
        action_group = ttk.LabelFrame(self.content, text="ボタン配置", padding=8)
        action_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        action_group.columnconfigure(0, weight=1)
        row += 1

        # ファイル選択
        file_row = ttk.Frame(file_group)
        file_row.grid(row=0, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)

        self.path_entry = ttk.Entry(file_row, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        ttk.Button(file_row, text="選択", command=self.select_file).grid(row=0, column=1, sticky="e")

        ttk.Label(
            file_group,
            text=(
                "ボタン配置の設定ファイルは通常、次の場所にあります。\n"
                "%USERPROFILE%\\AppData\\LocalLow\\bokura\\[アジア版やSteam版などのフォルダ]\\ \n"
                "localsave\\Env1\\[数字のフォルダ]\\[キャラクターUIDのフォルダ]\\localsave.bytes (2 KB以上)"
            ),
            justify="left"
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        sub_row = 0

        self.helper1_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="補助キー1",
            variable=self.helper1_var,
            values=[label for _, label in HELPER_OPTIONS],
            width=9,
        )
        sub_row += 1

        self.helper2_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="補助キー2",
            variable=self.helper2_var,
            values=[label for _, label in HELPER_OPTIONS],
            width=9,
        )
        sub_row += 1

        self.preset_combobox = self._add_top_combo_row(
            parent=keybind_group,
            row=sub_row,
            label="確認/キャンセル",
            variable=self.preset_var,
            values=[label for _, label in PRESET_OPTIONS],
            width=9,
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
        return combo

    def _add_action_row(self, parent: ttk.Frame, row: int, action: dict):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text=action["name"]).grid(row=0, column=0, sticky="w")

        var = tk.StringVar()
        combo = ttk.Combobox(
            frame,
            textvariable=var,
            values=list(BASE_ACTION_COMBO_VALUES),
            state="readonly",
            width=9,
            justify="right",
        )
        combo.grid(row=0, column=1, sticky="e")

        self.combo_vars[action["name"]] = var
        self.comboboxes[action["name"]] = combo

    def _bind_traces(self):
        self.preset_var.trace_add("write", self._on_any_value_changed)
        self.helper1_var.trace_add("write", self._on_helper1_changed)
        self.helper2_var.trace_add("write", self._on_helper2_changed)

        for var in self.combo_vars.values():
            var.trace_add("write", self._on_any_value_changed)

    def _bind_mousewheel(self):
        def _on_mousewheel(event):
            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

        def _on_mousewheel_linux_up(event):
            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(-1, "units")
                return "break"

        def _on_mousewheel_linux_down(event):
            if not self._can_scroll_vertical():
                return "break"
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(1, "units")
                return "break"

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.canvas.bind_all("<Button-4>", _on_mousewheel_linux_up)
        self.canvas.bind_all("<Button-5>", _on_mousewheel_linux_down)

    def find_anchor(self, dec: bytes, anchor: bytes) -> int:
        pos = dec.find(anchor)
        if pos < 0:
            raise ValueError("必須データが見つかりません。")
        return pos

    def get_input_offsets(self, action: dict) -> list[int]:
        if self.input_anchor_pos is None:
            raise ValueError("入力設定が読み込まれていません。")
        return [self.input_anchor_pos + rel for rel in action["rel_offsets"]]

    def get_preset_offset(self) -> int:
        if self.preset_anchor_pos is None:
            raise ValueError("確認/キャンセル設定が読み込まれていません。")
        return self.preset_anchor_pos + PRESET_REL_OFFSET

    def get_helper1_main_offset(self) -> int:
        if self.input_anchor_pos is None:
            raise ValueError("補助キー設定が読み込まれていません。")
        return self.input_anchor_pos + HELPER1_MAIN_REL_OFFSET

    def get_helper2_main_offset(self) -> int:
        if self.input_anchor_pos is None:
            raise ValueError("補助キー設定が読み込まれていません。")
        return self.input_anchor_pos + HELPER2_MAIN_REL_OFFSET

    def _ensure_combo_has_value(self, action_name: str, value: int, label: str):
        combo = self.comboboxes[action_name]
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values
        LABEL_TO_VALUE[label] = value

    def _ensure_preset_has_value(self, value: int, label: str):
        if self.preset_combobox is None:
            return
        current_values = list(self.preset_combobox["values"])
        if label not in current_values:
            current_values.append(label)
            self.preset_combobox["values"] = current_values
        PRESET_LABEL_TO_VALUE[label] = value

    def _ensure_helper_has_value(self, which: str, value: int, label: str):
        combo = self.helper1_combobox if which == "helper1" else self.helper2_combobox
        if combo is None:
            return
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values
        HELPER_LABEL_TO_VALUE[label] = value

    def _get_blocked_action_values(self) -> set[int]:
        blocked = set()

        helper1_label = self.helper1_var.get()
        if helper1_label in HELPER_LABEL_TO_VALUE:
            helper1_main_value = HELPER_LABEL_TO_VALUE[helper1_label]
            action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper1_main_value)
            if action_value is not None:
                blocked.add(action_value)

        helper2_label = self.helper2_var.get()
        if helper2_label in HELPER_LABEL_TO_VALUE:
            helper2_main_value = HELPER_LABEL_TO_VALUE[helper2_label]
            action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper2_main_value)
            if action_value is not None:
                blocked.add(action_value)

        return blocked

    def _refresh_action_combobox_choices(self):
        blocked_values = self._get_blocked_action_values()

        allowed_labels = [
            label for value, label in KEY_OPTIONS
            if value not in blocked_values
        ]

        for name, combo in self.comboboxes.items():
            current = self.combo_vars[name].get()
            values = list(allowed_labels)
            if current and current not in values:
                values.append(current)
            combo["values"] = values

    def _on_any_value_changed(self, *args):
        if self._suspend_events:
            return
        self.update_save_button_state()

    def _clear_conflicts_for_helper_value(self, helper_main_value: int, other_helper: str):
        action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper_main_value)
        if action_value is None:
            return

        for var in self.combo_vars.values():
            label = var.get()
            if not label:
                continue
            value = LABEL_TO_VALUE.get(label)
            if value == action_value:
                var.set("")

        other_var = self.helper1_var if other_helper == "helper1" else self.helper2_var
        other_label = other_var.get()
        if other_label:
            other_value = HELPER_LABEL_TO_VALUE.get(other_label)
            if other_value == helper_main_value:
                other_var.set("")

    def _on_helper1_changed(self, *args):
        if self._suspend_events:
            return

        self._suspend_events = True
        try:
            label = self.helper1_var.get()
            if label:
                value = HELPER_LABEL_TO_VALUE.get(label)
                if value is not None:
                    self._clear_conflicts_for_helper_value(value, other_helper="helper2")
            self._refresh_action_combobox_choices()
        finally:
            self._suspend_events = False

        self.update_save_button_state()

    def _on_helper2_changed(self, *args):
        if self._suspend_events:
            return

        self._suspend_events = True
        try:
            label = self.helper2_var.get()
            if label:
                value = HELPER_LABEL_TO_VALUE.get(label)
                if value is not None:
                    self._clear_conflicts_for_helper_value(value, other_helper="helper1")
            self._refresh_action_combobox_choices()
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
            self.status_var.set("ファイル未選択")
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
            "title": "セーブデータを選択",
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

        try:
            file_path = Path(path)
            raw = file_path.read_bytes()
            dec = brotli.decompress(raw)

            self.input_anchor_pos = self.find_anchor(dec, INPUT_ANCHOR)
            self.preset_anchor_pos = self.find_anchor(dec, PRESET_ANCHOR)

            for action in ACTIONS:
                for off in self.get_input_offsets(action):
                    if off >= len(dec):
                        raise ValueError("ファイルの形式が想定と異なります。")

            if self.get_preset_offset() >= len(dec):
                raise ValueError("ファイルの形式が想定と異なります。")

            for off in (self.get_helper1_main_offset(), self.get_helper2_main_offset()):
                if off + 3 >= len(dec):
                    raise ValueError("ファイルの形式が想定と異なります。")

            self.file_path = file_path
            self.original_dec = dec
            self.path_var.set(str(file_path))

            self._suspend_events = True
            try:
                self._load_values_from_dec(dec)
                self._refresh_action_combobox_choices()
            finally:
                self._suspend_events = False

            if self.reset_button is not None:
                self.reset_button.config(state="normal")

            self.base_status_message = "読み込み完了"
            self.update_save_button_state()

        except Exception:
            self.file_path = None
            self.original_dec = None
            self.path_var.set("")
            self.base_status_message = "読み込み失敗"
            self.update_save_button_state()
            messagebox.showerror(
                "読み込みエラー",
                "ファイルの読み込みに失敗しました。\n対応していないファイルか、データが破損している可能性があります。"
            )

    def _load_values_from_dec(self, dec: bytes):
        preset_off = self.get_preset_offset()
        preset_value = dec[preset_off]
        preset_label = PRESET_VALUE_TO_LABEL.get(preset_value)
        if preset_label is None:
            preset_label = "不明"
            self._ensure_preset_has_value(preset_value, preset_label)
        self.preset_var.set(preset_label)

        helper1_off = self.get_helper1_main_offset()
        helper1_value = int.from_bytes(dec[helper1_off:helper1_off + 4], "little")
        helper1_label = HELPER_VALUE_TO_LABEL.get(helper1_value)
        if helper1_label is None:
            helper1_label = "不明"
            self._ensure_helper_has_value("helper1", helper1_value, helper1_label)
        self.helper1_var.set(helper1_label)

        helper2_off = self.get_helper2_main_offset()
        helper2_value = int.from_bytes(dec[helper2_off:helper2_off + 4], "little")
        helper2_label = HELPER_VALUE_TO_LABEL.get(helper2_value)
        if helper2_label is None:
            helper2_label = "不明"
            self._ensure_helper_has_value("helper2", helper2_value, helper2_label)
        self.helper2_var.set(helper2_label)

        for action in ACTIONS:
            name = action["name"]
            offsets = self.get_input_offsets(action)
            first_value = dec[offsets[0]]

            label = VALUE_TO_LABEL.get(first_value)
            if label is None:
                label = "不明"
                self._ensure_combo_has_value(name, first_value, label)

            self.combo_vars[name].set(label)

    def reset_values(self):
        if self.original_dec is None:
            return

        self._suspend_events = True
        try:
            self._load_values_from_dec(self.original_dec)
            self._refresh_action_combobox_choices()
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

            preset_label = self.preset_var.get()
            if preset_label not in PRESET_LABEL_TO_VALUE:
                raise ValueError("確認/キャンセルの値が不正です。")
            dec[self.get_preset_offset()] = PRESET_LABEL_TO_VALUE[preset_label]

            helper1_label = self.helper1_var.get()
            if helper1_label not in HELPER_LABEL_TO_VALUE:
                raise ValueError("補助キー1の値が不正です。")
            helper1_value = HELPER_LABEL_TO_VALUE[helper1_label]
            helper1_off = self.get_helper1_main_offset()
            dec[helper1_off:helper1_off + 4] = helper1_value.to_bytes(4, "little")

            helper2_label = self.helper2_var.get()
            if helper2_label not in HELPER_LABEL_TO_VALUE:
                raise ValueError("補助キー2の値が不正です。")
            helper2_value = HELPER_LABEL_TO_VALUE[helper2_label]
            helper2_off = self.get_helper2_main_offset()
            dec[helper2_off:helper2_off + 4] = helper2_value.to_bytes(4, "little")

            for action in ACTIONS:
                name = action["name"]
                selected_label = self.combo_vars[name].get()
                if selected_label not in LABEL_TO_VALUE:
                    raise ValueError(f"{name} の値が不正です。")

                value = LABEL_TO_VALUE[selected_label]
                for off in self.get_input_offsets(action):
                    dec[off] = value

            enc = brotli.compress(bytes(dec), quality=1)
            self.file_path.write_bytes(enc)

            self.original_dec = bytes(dec)

            self._suspend_events = True
            try:
                self._load_values_from_dec(self.original_dec)
                self._refresh_action_combobox_choices()
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