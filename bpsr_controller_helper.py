import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
import json
from typing import Optional
import brotli

# =========================
# ゲームパッドのキー値テーブル（アクション側 4 byte）
# =========================
KEY_OPTIONS = [
    (1,  "L前後入力"),
    (2,  "L左右入力"),
    (3,  "R前後入力"),
    (4,  "R左右入力"),
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

CONTROLLER_AXIS_VALUES = {1, 2, 3, 4}

# 方向入力以外のアクションにも、L/Rスティックの各方向入力を割り当て可能にする。
# 方向入力アクション自身は、後段の CONTROLLER_DIRECTION_ACTION_NAMES で
# L前後 / L左右 / R前後 / R左右の4択に限定する。
CONTROLLER_ASSIGNABLE_VALUES = [
    value for value, _ in KEY_OPTIONS
]
BASE_ACTION_COMBO_VALUES = [
    VALUE_TO_LABEL[value]
    for value in CONTROLLER_ASSIGNABLE_VALUES
]

ACTION_STATE_SINGLE = 0xFFFFFFFF
ACTION_STATE_HELPER1 = 0x00000000
ACTION_STATE_HELPER2 = 0x00000001

ACTION_HELPER_NONE_LABEL = "割り当てなし"
DETECTED_SAVE_MANUAL_LABEL = "設定ファイルを手動選択しました"
BUTTON_LAYOUT_FILE_NAME = "bpsr_controller_helper_config.json"

CONTROLLER_OPTIONS = ["PlayStation", "Nintendo", "Xbox"]
KEYMOUSE_DEVICE = "キーボード/マウス"
INPUT_DEVICE_OPTIONS = [*CONTROLLER_OPTIONS]
SAVED_INPUT_DEVICE_OPTIONS = [*CONTROLLER_OPTIONS, KEYMOUSE_DEVICE]
DEFAULT_CONTROLLER = "PlayStation"

CONTROLLER_DISPLAY_MAPS = {
    "PlayStation": {
        1: "L前後入力",
        2: "L左右入力",
        3: "R前後入力",
        4: "R左右入力",
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
        1: "L前後入力",
        2: "L左右入力",
        3: "R前後入力",
        4: "R左右入力",
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
        1: "L前後入力",
        2: "L左右入力",
        3: "R前後入力",
        4: "R左右入力",
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
# アンカー# =========================
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
# ゲームパッドごとに表示を切り替える
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
# ゲームパッドの既知アクション一覧
# 既存の並びを維持しつつ、Excelで確定した不明以外のアクションを追加
# =========================
ACTIONS = [
    {'name': '移動-前後', 'rel_offsets': [0x000B2], 'allowed_values': [0x00000001]},
    {'name': '移動-左右', 'rel_offsets': [0x000C7], 'allowed_values': [0x00000002]},
    {'name': 'カメラ-前後', 'rel_offsets': [0x0060F], 'allowed_values': [0x00000003]},
    {'name': 'カメラ-左右', 'rel_offsets': [0x00624], 'allowed_values': [0x00000004]},
    {'name': 'ジャンプ', 'rel_offsets': [0x00133]},
    {'name': 'ダッシュ/回避', 'rel_offsets': [0x001C7]},
    {'name': '環境共鳴能力1', 'rel_offsets': [0x00204]},
    {'name': '環境共鳴能力2', 'rel_offsets': [0x00227]},
    {'name': '通常攻撃', 'rel_offsets': [0x0027E]},
    {'name': '特殊攻撃', 'rel_offsets': [0x009E7]},
    {'name': 'マスタリースキル1', 'rel_offsets': [0x002D5]},
    {'name': 'マスタリースキル2', 'rel_offsets': [0x00312]},
    {'name': 'マスタリースキル3', 'rel_offsets': [0x0034F]},
    {'name': 'マスタリースキル4', 'rel_offsets': [0x0038C]},
    {'name': '究極スキル', 'rel_offsets': [0x009AA]},
    {'name': 'バトルイマジン1', 'rel_offsets': [0x00A24]},
    {'name': 'バトルイマジン2', 'rel_offsets': [0x00A61]},
    {'name': '左でアイテム切り替え', 'rel_offsets': [0x0102D]},
    {'name': 'アイテム使用', 'rel_offsets': [0x003C9]},
    {'name': '右でアイテム切り替え', 'rel_offsets': [0x0106A]},
    {'name': 'アクション', 'rel_offsets': [0x00551, 0x0158F]},
    {'name': 'ロックオン/切り替え', 'rel_offsets': [0x00406]},
    {'name': 'エクストラスキル', 'rel_offsets': [0x00A9E]},
    {'name': 'インタラクト解除', 'rel_offsets': [0x0045D]},
    {'name': 'クエスト追跡', 'rel_offsets': [0x00514]},
    {'name': 'UI非表示', 'rel_offsets': [0x004D7]},
    {'name': 'クエストアイテムのクイック使用', 'rel_offsets': [0x0049A]},
    {'name': 'マップON/OFF', 'rel_offsets': [0x00690]},
    {'name': 'クエスト', 'rel_offsets': [0x006CD]},
    {'name': 'ソーシャルモード', 'rel_offsets': [0x0070A]},
    {'name': 'メニューを開く', 'rel_offsets': [0x0084D]},
    {'name': 'メニューを閉じる', 'rel_offsets': [0x017CE]},
    {'name': 'カーソル移動-上下', 'rel_offsets': [0x01F40]},
    {'name': 'カーソル移動-左右', 'rel_offsets': [0x01F63]},
    {'name': '撮影', 'rel_offsets': [0x0076A]},
    {'name': 'ダンジョン退出', 'rel_offsets': [0x00810]},
    {'name': 'アイテムを使用', 'rel_offsets': [0x0090D, 0x0186B]},
    {'name': 'クイック操作', 'rel_offsets': [0x00BA4]},
    {'name': '乗り物召喚/解除', 'rel_offsets': [0x00B44]},
    {'name': '招待承認', 'rel_offsets': [0x00BE1, 0x01A89]},
    {'name': '招待拒否', 'rel_offsets': [0x00C1E, 0x01AC6]},
    {'name': 'オートバトル', 'rel_offsets': [0x00CBB]},
    {'name': 'チャンネル', 'rel_offsets': [0x00C7E]},
    {'name': 'イラストガイド', 'rel_offsets': [0x00CF8]},
    {'name': 'クイックホイール', 'rel_offsets': [0x00D35]},
    {'name': 'クイックホイール切替（左）', 'rel_offsets': [0x0289C]},
    {'name': 'クイックホイール切替（右）', 'rel_offsets': [0x028B1]},
    {'name': 'クイックホイール編集', 'rel_offsets': [0x028EE]},
    {'name': 'クエスト切り替え（左）', 'rel_offsets': [0x00FB3]},
    {'name': 'クエスト切り替え（右）', 'rel_offsets': [0x00FD6]},
    {'name': 'ズームアウト', 'rel_offsets': [0x0058E]},
    {'name': 'ズームイン', 'rel_offsets': [0x005A3]},
    {'name': 'スキルパレットを開く', 'rel_offsets': [0x01227, 0x01F7D]},
    {'name': 'ロールスキル1', 'rel_offsets': [0x01133]},
    {'name': 'ロールスキル2', 'rel_offsets': [0x01170]},
    {'name': 'ロールスキル3', 'rel_offsets': [0x011AD]},
    {'name': 'ロールスキル4', 'rel_offsets': [0x011EA]},
    {'name': 'ホーム設計図', 'rel_offsets': [0x0124A]},
    {'name': '撮影モードカメラ移動-上下', 'rel_offsets': [0x0230E]},
    {'name': '撮影モードカメラ移動-左右', 'rel_offsets': [0x02323]},
    {'name': '撮影モードカメラパン-前後', 'rel_offsets': [0x0239F]},
    {'name': '撮影モードカメラパン-左右', 'rel_offsets': [0x023B4]},
    {'name': '撮影モード画面を非表示にする', 'rel_offsets': [0x021B8]},
    {'name': '撮影モード撮影', 'rel_offsets': [0x0213E]},
    {'name': '撮影モード設定メニュー', 'rel_offsets': [0x02688]},
    {'name': '撮影モード参加者メニュー', 'rel_offsets': [0x026C5]},
    {'name': '撮影モードカーソル呼出し', 'rel_offsets': [0x027B8]},
    {'name': '撮影モードメニューを閉じる', 'rel_offsets': [0x0226F]},
    {'name': '撮影モード移動-前後', 'rel_offsets': [0x02430], 'allowed_values': [0x00000001]},
    {'name': '撮影モード移動-左右', 'rel_offsets': [0x02445], 'allowed_values': [0x00000002]},
    {'name': '撮影モードカメラ-前後', 'rel_offsets': [0x0273A], 'allowed_values': [0x00000003]},
    {'name': '撮影モードカメラ-左右', 'rel_offsets': [0x0274F], 'allowed_values': [0x00000004]},
    {'name': '撮影モードジャンプ', 'rel_offsets': [0x0205D]},
    {'name': '撮影モードダッシュ/回避', 'rel_offsets': [0x0217B]},
    {'name': '撮影モード特殊攻撃', 'rel_offsets': [0x024B1]},
    {'name': '撮影モードマスタリースキル1', 'rel_offsets': [0x024EE]},
    {'name': '撮影モードマスタリースキル2', 'rel_offsets': [0x0252B]},
    {'name': '撮影モードマスタリースキル3', 'rel_offsets': [0x02568]},
    {'name': '撮影モードマスタリースキル4', 'rel_offsets': [0x025A5]},
    {'name': '撮影モード究極スキル', 'rel_offsets': [0x0209A]},
    {'name': '撮影モード乗り物召喚/解除', 'rel_offsets': [0x025E2]},
    {'name': '撮影モードカーソル移動-上下', 'rel_offsets': [0x027FE]},
    {'name': '撮影モードカーソル移動-左右', 'rel_offsets': [0x02821]},
    {'name': '撮影モードズームアウト', 'rel_offsets': [0x020EC]},
    {'name': '撮影モードズームイン', 'rel_offsets': [0x02101]},
    {'name': '釣りモード竿移動-前後', 'rel_offsets': [0x02BB0], 'allowed_values': [0x00000001]},
    {'name': '釣りモード竿移動-左右', 'rel_offsets': [0x02BC5], 'allowed_values': [0x00000002]},
    {'name': '釣りモードキャスト/竿を引く', 'rel_offsets': [0x029A3]},
    {'name': '釣りモード釣り/図鑑', 'rel_offsets': [0x029E0]},
    {'name': '釣りモード釣り/研究', 'rel_offsets': [0x02A1D]},
    {'name': '釣りモード釣り餌切替', 'rel_offsets': [0x02A5A]},
    {'name': '釣りモード竿切替', 'rel_offsets': [0x02A97]},
    {'name': '釣りモードモード/ガイド', 'rel_offsets': [0x02AD4]},
    {'name': '釣りモード設定', 'rel_offsets': [0x02B11]},
    {'name': '釣りモードメニューを閉じる', 'rel_offsets': [0x02C3F]},
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
# キーボード/マウス用のキー一覧
# Excel「キー一覧」シートのキーボード / マウスをすべて収録
# =========================
KEYMOUSE_OPTIONS = [
    (0x00000001, 0x00000009, 'Tab'),
    (0x00000001, 0x0000000D, 'Enter'),
    (0x00000001, 0x0000001B, 'Esc'),
    (0x00000001, 0x00000020, 'Space'),
    (0x00000001, 0x00000027, ':'),
    (0x00000001, 0x0000002C, '<'),
    (0x00000001, 0x0000002D, '-'),
    (0x00000001, 0x0000002E, '>'),
    (0x00000001, 0x0000002F, '/'),
    (0x00000001, 0x00000030, '0'),
    (0x00000001, 0x00000031, '1'),
    (0x00000001, 0x00000032, '2'),
    (0x00000001, 0x00000033, '3'),
    (0x00000001, 0x00000034, '4'),
    (0x00000001, 0x00000035, '5'),
    (0x00000001, 0x00000036, '6'),
    (0x00000001, 0x00000037, '7'),
    (0x00000001, 0x00000038, '8'),
    (0x00000001, 0x00000039, '9'),
    (0x00000001, 0x0000003B, ';'),
    (0x00000001, 0x0000003D, '^'),
    (0x00000001, 0x0000005B, '@'),
    (0x00000001, 0x0000005C, ']'),
    (0x00000001, 0x0000005D, '['),
    (0x00000001, 0x00000060, '~'),
    (0x00000001, 0x00000061, 'A'),
    (0x00000001, 0x00000062, 'B'),
    (0x00000001, 0x00000063, 'C'),
    (0x00000001, 0x00000064, 'D'),
    (0x00000001, 0x00000065, 'E'),
    (0x00000001, 0x00000066, 'F'),
    (0x00000001, 0x00000067, 'G'),
    (0x00000001, 0x00000068, 'H'),
    (0x00000001, 0x00000069, 'I'),
    (0x00000001, 0x0000006A, 'J'),
    (0x00000001, 0x0000006B, 'K'),
    (0x00000001, 0x0000006C, 'L'),
    (0x00000001, 0x0000006D, 'M'),
    (0x00000001, 0x0000006E, 'N'),
    (0x00000001, 0x0000006F, 'O'),
    (0x00000001, 0x00000070, 'P'),
    (0x00000001, 0x00000071, 'Q'),
    (0x00000001, 0x00000072, 'R'),
    (0x00000001, 0x00000073, 'S'),
    (0x00000001, 0x00000074, 'T'),
    (0x00000001, 0x00000075, 'U'),
    (0x00000001, 0x00000076, 'V'),
    (0x00000001, 0x00000077, 'W'),
    (0x00000001, 0x00000078, 'X'),
    (0x00000001, 0x00000079, 'Y'),
    (0x00000001, 0x0000007A, 'Z'),
    (0x00000001, 0x00000100, 'Num0'),
    (0x00000001, 0x00000101, 'Num1'),
    (0x00000001, 0x00000102, 'Num2'),
    (0x00000001, 0x00000103, 'Num3'),
    (0x00000001, 0x00000104, 'Num4'),
    (0x00000001, 0x00000105, 'Num5'),
    (0x00000001, 0x00000106, 'Num6'),
    (0x00000001, 0x00000107, 'Num7'),
    (0x00000001, 0x00000108, 'Num8'),
    (0x00000001, 0x00000109, 'Num9'),
    (0x00000001, 0x00000111, '↑'),
    (0x00000001, 0x00000112, '↓'),
    (0x00000001, 0x00000113, '→'),
    (0x00000001, 0x00000114, '←'),
    (0x00000001, 0x0000011A, 'F1'),
    (0x00000001, 0x0000011B, 'F2'),
    (0x00000001, 0x0000011C, 'F3'),
    (0x00000001, 0x0000011D, 'F4'),
    (0x00000001, 0x0000011E, 'F5'),
    (0x00000001, 0x0000011F, 'F6'),
    (0x00000001, 0x00000120, 'F7'),
    (0x00000001, 0x00000121, 'F8'),
    (0x00000001, 0x00000122, 'F9'),
    (0x00000001, 0x00000123, 'F10'),
    (0x00000001, 0x00000124, 'F11'),
    (0x00000001, 0x00000125, 'F12'),
    (0x00000001, 0x0000012F, 'R Shift'),
    (0x00000001, 0x00000130, 'L Shift'),
    (0x00000001, 0x00000131, 'R Ctrl'),
    (0x00000001, 0x00000132, 'L Ctrl'),
    (0x00000001, 0x00000133, 'R Alt'),
    (0x00000001, 0x00000134, 'L Alt'),
    (0x00000002, 0x00000000, 'マウス左クリック'),
    (0x00000002, 0x00000001, 'マウス右クリック'),
    (0x00000002, 0x00000002, 'マウス中央キー'),
    (0x00000002, 0x00000003, 'マウスボタン3'),
    (0x00000002, 0x00000004, 'マウスボタン4'),
    (0x00000002, 0x00000005, 'マウスボタン5'),
    (0x00000002, 0x00000006, 'マウスボタン6'),
    (0x00000002, 0x00000007, 'マウススクロール'),
]
KEYMOUSE_RECORD_TO_LABEL = {
    (input_type, value): label
    for input_type, value, label in KEYMOUSE_OPTIONS
}
KEYMOUSE_LABEL_TO_RECORD = {
    label: (input_type, value)
    for input_type, value, label in KEYMOUSE_OPTIONS
}
KEYMOUSE_COMBO_VALUES = [label for _, _, label in KEYMOUSE_OPTIONS]

# これらのキーボード/マウス操作は、ゲーム内では L Ctrl との同時入力として使う。
KEYMOUSE_LCTRL_PREFIX_ACTION_NAMES = {
    "UI非表示",
    "パーティボイス切り替え",
    "ロールスキル1",
    "ロールスキル2",
    "ロールスキル3",
    "ロールスキル4",
}

# =========================
# キーボード/マウスの既知アクション一覧
# Excel「アクション一覧」の不明アクション以外をすべて収録
# =========================
KEYMOUSE_ACTIONS = [
    {'name': '移動-前', 'rel_offsets': [0x00059, 0x012BD]},
    {'name': '移動-後', 'rel_offsets': [0x0006E, 0x012D2]},
    {'name': '移動-左', 'rel_offsets': [0x00083, 0x012E7]},
    {'name': '移動-右', 'rel_offsets': [0x00098, 0x012FC]},
    {'name': '歩く/走る切替', 'rel_offsets': [0x00156, 0x01371]},
    {'name': 'ジャンプ', 'rel_offsets': [0x00119, 0x0134E]},
    {'name': 'ダッシュ/回避1', 'rel_offsets': [0x00193, 0x013AE]},
    {'name': 'ダッシュ/回避2', 'rel_offsets': [0x001AD]},
    {'name': '環境共鳴能力1', 'rel_offsets': [0x001EA, 0x013D1]},
    {'name': '環境共鳴能力2', 'rel_offsets': [0x00241]},
    {'name': '通常攻撃', 'rel_offsets': [0x00264], 'allowed_input_types': [INPUT_TYPE_MOUSE]},
    {'name': '特殊攻撃', 'rel_offsets': [0x009CD, 0x01934]},
    {'name': 'マスタリースキル1', 'rel_offsets': [0x002BB, 0x0143A]},
    {'name': 'マスタリースキル2', 'rel_offsets': [0x002F8, 0x0145D]},
    {'name': 'マスタリースキル3', 'rel_offsets': [0x00335, 0x01480]},
    {'name': 'マスタリースキル4', 'rel_offsets': [0x00372, 0x014A3]},
    {'name': '究極スキル', 'rel_offsets': [0x00990, 0x01911]},
    {'name': 'バトルイマジン1', 'rel_offsets': [0x00A0A, 0x01957]},
    {'name': 'バトルイマジン2', 'rel_offsets': [0x00A47, 0x0197A]},
    {'name': '左でアイテム切り替え', 'rel_offsets': [0x01013, 0x01E28]},
    {'name': 'アイテム使用', 'rel_offsets': [0x003AF, 0x014C6]},
    {'name': '右でアイテム切り替え', 'rel_offsets': [0x01050, 0x01E4B]},
    {'name': 'アクション', 'rel_offsets': [0x00537, 0x01598]},
    {'name': 'ロックオン/切り替え1', 'rel_offsets': [0x003EC, 0x014E9]},
    {'name': 'ロックオン/切り替え2', 'rel_offsets': [0x00420]},
    {'name': 'エクストラスキル', 'rel_offsets': [0x00A84, 0x0199D]},
    {'name': 'インタラクト解除', 'rel_offsets': [0x00443, 0x0150C]},
    {'name': 'クエスト追跡', 'rel_offsets': [0x004FA, 0x01575]},
    {'name': 'UI非表示', 'rel_offsets': [0x004BD, 0x01552]},
    {'name': 'クエストアイテムのクイック使用', 'rel_offsets': [0x00480, 0x0152F]},
    {'name': 'おすすめイベント', 'rel_offsets': [0x00B07, 0x01A06]},
    {'name': 'マップON/OFF', 'rel_offsets': [0x00676, 0x01679]},
    {'name': 'クエスト', 'rel_offsets': [0x006B3, 0x0169C]},
    {'name': 'ソーシャルモード', 'rel_offsets': [0x006F0, 0x016BF]},
    {'name': 'トーク', 'rel_offsets': [0x00C41, 0x01B0C]},
    {'name': 'キャラクター', 'rel_offsets': [0x0072D, 0x016E2]},
    {'name': 'ギルド', 'rel_offsets': [0x00E70, 0x01CD3]},
    {'name': 'チャット画面チャンネル切り替え-上', 'rel_offsets': [0x0108D]},
    {'name': 'チャット画面チャンネル切り替え-下', 'rel_offsets': [0x010B0]},
    {'name': 'チャット入力チャンネル切り替え-左', 'rel_offsets': [0x010D3]},
    {'name': 'チャット入力チャンネル切り替え-右', 'rel_offsets': [0x010F6]},
    {'name': 'メニューを開く', 'rel_offsets': [0x00833]},
    {'name': 'メニューを閉じる', 'rel_offsets': [0x017B4]},
    {'name': 'マウス呼出し', 'rel_offsets': [0x00870, 0x017F1]},
    {'name': '撮影', 'rel_offsets': [0x00750, 0x01705]},
    {'name': '所持品', 'rel_offsets': [0x0078D, 0x01728]},
    {'name': 'パーティ', 'rel_offsets': [0x007B0, 0x0174B]},
    {'name': 'シーズンセンター', 'rel_offsets': [0x007D3, 0x0176E]},
    {'name': 'ダンジョン退出', 'rel_offsets': [0x007F6, 0x01791]},
    {'name': 'アビリティ', 'rel_offsets': [0x008D0, 0x01851]},
    {'name': 'アイテムを使用', 'rel_offsets': [0x008F3, 0x01874]},
    {'name': 'クイック操作', 'rel_offsets': [0x00B8A, 0x01A6F]},
    {'name': '乗り物召喚/解除', 'rel_offsets': [0x00B2A, 0x01A29]},
    {'name': 'パーティボイス切り替え', 'rel_offsets': [0x00B67, 0x01A4C]},
    {'name': '招待承認', 'rel_offsets': [0x00BC7, 0x01A92]},
    {'name': '招待拒否', 'rel_offsets': [0x00C04, 0x01ACF]},
    {'name': 'オートバトル', 'rel_offsets': [0x00CA1, 0x01B52]},
    {'name': 'チャンネル', 'rel_offsets': [0x00C64, 0x01B2F]},
    {'name': 'イラストガイド', 'rel_offsets': [0x00CDE, 0x01B75]},
    {'name': 'クイックホイール', 'rel_offsets': [0x00D1B, 0x01B98]},
    {'name': 'クイックホイール切替', 'rel_offsets': [0x02882]},
    {'name': 'クイックホイール編集', 'rel_offsets': [0x028D4]},
    {'name': 'オートラン', 'rel_offsets': [0x00F39, 0x01D9C]},
    {'name': 'クエスト切り替え（左）', 'rel_offsets': [0x00F99, 0x01DE2]},
    {'name': 'クエスト切り替え（右）', 'rel_offsets': [0x00FF0]},
    {'name': 'ホーム編集', 'rel_offsets': [0x00F16, 0x01D79]},
    {'name': 'ズームアウト/ズームイン', 'rel_offsets': [0x00574, 0x00893, 0x015D5, 0x01814]},
    {'name': 'スキルパレットを開く', 'rel_offsets': [0x0120D, 0x01F86]},
    {'name': 'ロールスキル1', 'rel_offsets': [0x01119]},
    {'name': 'ロールスキル2', 'rel_offsets': [0x01156]},
    {'name': 'ロールスキル3', 'rel_offsets': [0x01193]},
    {'name': 'ロールスキル4', 'rel_offsets': [0x011D0]},
    {'name': 'ホーム設計図', 'rel_offsets': [0x01264, 0x01FDD]},
    {'name': 'アテンドイマジンを召喚する', 'rel_offsets': [0x01287, 0x02000]},
    {'name': 'クイックホイール-スロット1', 'rel_offsets': [0x00D58, 0x01BBB]},
    {'name': 'クイックホイール-スロット2', 'rel_offsets': [0x00D7B, 0x01BDE]},
    {'name': 'クイックホイール-スロット3', 'rel_offsets': [0x00D9E, 0x01C01]},
    {'name': 'クイックホイール-スロット4', 'rel_offsets': [0x00DC1, 0x01C24]},
    {'name': 'クイックホイール-スロット5', 'rel_offsets': [0x00DE4, 0x01C47]},
    {'name': 'クイックホイール-スロット6', 'rel_offsets': [0x00E07, 0x01C6A]},
    {'name': 'クイックホイール-スロット7', 'rel_offsets': [0x00E2A, 0x01C8D]},
    {'name': 'クイックホイール-スロット8', 'rel_offsets': [0x00E4D, 0x01CB0]},
    {'name': 'スキル', 'rel_offsets': [0x00E93, 0x01CF6]},
    {'name': '装備', 'rel_offsets': [0x00EB6, 0x01D19]},
    {'name': '撮影モードカメラ移動-上', 'rel_offsets': [0x022B5]},
    {'name': '撮影モードカメラ移動-下', 'rel_offsets': [0x022CA]},
    {'name': '撮影モードカメラ移動-左', 'rel_offsets': [0x022DF]},
    {'name': '撮影モードカメラ移動-右', 'rel_offsets': [0x022F4]},
    {'name': '撮影モードカメラパン-前', 'rel_offsets': [0x02346]},
    {'name': '撮影モードカメラパン-後', 'rel_offsets': [0x0235B]},
    {'name': '撮影モードカメラパン-左', 'rel_offsets': [0x02370]},
    {'name': '撮影モードカメラパン-右', 'rel_offsets': [0x02385]},
    {'name': '撮影モードズームアウト', 'rel_offsets': [0x020BD]},
    {'name': '撮影モードズームイン', 'rel_offsets': [0x020D2]},
    {'name': '撮影モード画面を非表示にする', 'rel_offsets': [0x0219E]},
    {'name': '撮影モード撮影', 'rel_offsets': [0x02124]},
    {'name': '撮影モード設定メニュー', 'rel_offsets': [0x0266E]},
    {'name': '撮影モード参加者メニュー', 'rel_offsets': [0x026AB]},
    {'name': '撮影モード移動-前', 'rel_offsets': [0x023D7]},
    {'name': '撮影モード移動-後', 'rel_offsets': [0x023EC]},
    {'name': '撮影モード移動-左', 'rel_offsets': [0x02401]},
    {'name': '撮影モード移動-右', 'rel_offsets': [0x02416]},
    {'name': '撮影モードジャンプ', 'rel_offsets': [0x02043]},
    {'name': '撮影モードダッシュ/回避', 'rel_offsets': [0x02161]},
    {'name': '撮影モード歩く/走る切替', 'rel_offsets': [0x026E8]},
    {'name': '撮影モード特殊攻撃', 'rel_offsets': [0x02497]},
    {'name': '撮影モードマスタリースキル1', 'rel_offsets': [0x024D4]},
    {'name': '撮影モードマスタリースキル2', 'rel_offsets': [0x02511]},
    {'name': '撮影モードマスタリースキル3', 'rel_offsets': [0x0254E]},
    {'name': '撮影モードマスタリースキル4', 'rel_offsets': [0x0258B]},
    {'name': '撮影モード究極スキル', 'rel_offsets': [0x02080]},
    {'name': '撮影モード乗り物召喚/解除', 'rel_offsets': [0x025C8]},
    {'name': '撮影モード撮影モード終了', 'rel_offsets': [0x02605]},
    {'name': '撮影モードメニューを閉じる', 'rel_offsets': [0x02255]},
    {'name': '釣りモードキャスト/竿を引く', 'rel_offsets': [0x02989]},
    {'name': '釣りモード竿移動-前', 'rel_offsets': [0x02B57]},
    {'name': '釣りモード竿移動-後', 'rel_offsets': [0x02B6C]},
    {'name': '釣りモード竿移動-左', 'rel_offsets': [0x02B81]},
    {'name': '釣りモード竿移動-右', 'rel_offsets': [0x02B96]},
    {'name': '釣りモード釣り/図鑑', 'rel_offsets': [0x029C6]},
    {'name': '釣りモード釣り/研究', 'rel_offsets': [0x02A03]},
    {'name': '釣りモード釣り餌切替', 'rel_offsets': [0x02A40]},
    {'name': '釣りモード竿切替', 'rel_offsets': [0x02A7D]},
    {'name': '釣りモードモード/ガイド', 'rel_offsets': [0x02ABA]},
    {'name': '釣りモード設定', 'rel_offsets': [0x02AF7]},
    {'name': '釣りモードマウス呼出し', 'rel_offsets': [0x02B34]},
    {'name': '釣りモードメニューを閉じる', 'rel_offsets': [0x02C25]},
]

# =========================
# lodef / UU1 兼用補正
# 一部アクションでは controller と keymouse の並びが入れ替わる。
# ACTIONS / KEYMOUSE_ACTIONS 自体は保持し、typeで実際のvalue位置を選ぶ。
# =========================
ACTION_CONTROLLER_OFFSET_ALIASES = {
    "環境共鳴能力2": [0x00241],
    "クエスト切り替え（右）": [0x00FF0],
    "ホーム設計図": [0x01264],
}

ACTION_KEYMOUSE_OFFSET_ALIASES = {
    "環境共鳴能力2": [0x00227],
    "クエスト切り替え（右）": [0x00FD6],
    "ホーム設計図": [0x0124A],
}


# =========================
# 撮影モード / 釣りモードのキー設定
# 同じ役割の通常アクションが存在するモード側アクションは、
# 単独設定をオフにすると通常アクションへ追従する。
# =========================
PHOTO_MODE_PREFIX = "撮影モード"
FISHING_MODE_PREFIX = "釣りモード"
MODE_PREFIXES = (PHOTO_MODE_PREFIX, FISHING_MODE_PREFIX)

# この撮影モードアクションは、通常アクションと同名でも自動連動しない。
# 「撮影モードのアクションを単独で設定する」がオフでも、個別に編集できる。
PHOTO_MODE_UNLINKED_ACTION_NAMES = {
    "撮影モード撮影",
}

# ゲームパッド側だけ、通常の「メニューを閉じる」と連動させない。
CONTROLLER_PHOTO_MODE_UNLINKED_ACTION_NAMES = (
    PHOTO_MODE_UNLINKED_ACTION_NAMES
    | {"撮影モードメニューを閉じる"}
)
CONTROLLER_FISHING_MODE_UNLINKED_ACTION_NAMES = {
    "釣りモードメニューを閉じる",
}

FISHING_MODE_UNLINKED_ACTION_NAMES: set[str] = set()


def _is_mode_action_name(action_name: str) -> bool:
    return action_name.startswith(MODE_PREFIXES)


CONTROLLER_DIRECTION_ACTION_NAMES = {
    "移動-前後",
    "移動-左右",
    "カメラ-前後",
    "カメラ-左右",
    "カーソル移動-上下",
    "カーソル移動-左右",
    "撮影モードカメラ移動-上下",
    "撮影モードカメラ移動-左右",
    "撮影モードカメラパン-前後",
    "撮影モードカメラパン-左右",
    "撮影モード移動-前後",
    "撮影モード移動-左右",
    "撮影モードカメラ-前後",
    "撮影モードカメラ-左右",
    "撮影モードカーソル移動-上下",
    "撮影モードカーソル移動-左右",
    "釣りモード竿移動-前後",
    "釣りモード竿移動-左右",
}

# 方向入力はすべて、L前後 / L左右 / R前後 / R左右の4択と補助キーに対応させる。
for _direction_action in ACTIONS:
    if _direction_action["name"] in CONTROLLER_DIRECTION_ACTION_NAMES:
        _direction_action["allowed_values"] = [1, 2, 3, 4]
        _direction_action["uses_helper"] = True
del _direction_action

CONTROLLER_MAIN_ACTIONS = [
    action for action in ACTIONS
    if not _is_mode_action_name(action["name"])
]
CONTROLLER_PHOTO_MODE_ACTIONS = [
    action for action in ACTIONS
    if action["name"].startswith(PHOTO_MODE_PREFIX)
]
CONTROLLER_FISHING_MODE_ACTIONS = [
    action for action in ACTIONS
    if action["name"].startswith(FISHING_MODE_PREFIX)
]
KEYMOUSE_MAIN_ACTIONS = [
    action for action in KEYMOUSE_ACTIONS
    if not _is_mode_action_name(action["name"])
]
KEYMOUSE_PHOTO_MODE_ACTIONS = [
    action for action in KEYMOUSE_ACTIONS
    if action["name"].startswith(PHOTO_MODE_PREFIX)
]
KEYMOUSE_FISHING_MODE_ACTIONS = [
    action for action in KEYMOUSE_ACTIONS
    if action["name"].startswith(FISHING_MODE_PREFIX)
]


def _build_mode_links(
    actions: list[dict],
    mode_prefix: str,
    exception_normal_to_mode: dict[str, str],
    unlinked_action_names: set[str],
) -> dict[str, str]:
    """モード側アクション名 -> 通常側アクション名 の対応を作る。"""
    normal_names = {
        action["name"]
        for action in actions
        if not _is_mode_action_name(action["name"])
    }
    mode_names = {
        action["name"]
        for action in actions
        if action["name"].startswith(mode_prefix)
    }

    # 例外は「通常アクション名: モード側アクション名」で定義する。
    resolved_exceptions = {
        mode_name: normal_name
        for normal_name, mode_name in exception_normal_to_mode.items()
        if normal_name in normal_names and mode_name in mode_names
    }
    exception_normal_names = set(resolved_exceptions.values())

    links: dict[str, str] = {}
    for mode_name in mode_names:
        if mode_name in unlinked_action_names:
            continue

        suffix = mode_name.removeprefix(mode_prefix)
        # 例外で同じ通常アクションの対応先が指定されている場合、
        # 接尾辞一致の候補より例外側を優先する。
        if suffix in normal_names and suffix not in exception_normal_names:
            links[mode_name] = suffix

    links.update(resolved_exceptions)
    return links


CONTROLLER_PHOTO_MODE_LINKS = _build_mode_links(
    ACTIONS,
    PHOTO_MODE_PREFIX,
    {
    },
    CONTROLLER_PHOTO_MODE_UNLINKED_ACTION_NAMES,
)

KEYMOUSE_PHOTO_MODE_LINKS = _build_mode_links(
    KEYMOUSE_ACTIONS,
    PHOTO_MODE_PREFIX,
    {
        "カメラ-前": "撮影モードカメラパン-前",
        "カメラ-後": "撮影モードカメラパン-後",
        "カメラ-左": "撮影モードカメラパン-左",
        "カメラ-右": "撮影モードカメラパン-右",
        "ダッシュ/回避1": "撮影モードダッシュ/回避",
        "撮影": "撮影モード撮影モード終了",
    },
    PHOTO_MODE_UNLINKED_ACTION_NAMES,
)

# 釣りモードは、先頭の「釣りモード」を除いた名前が通常アクション名と
# 完全一致する場合だけ自動連動する。例外対応は不要。
CONTROLLER_FISHING_MODE_LINKS = _build_mode_links(
    ACTIONS,
    FISHING_MODE_PREFIX,
    {},
    CONTROLLER_FISHING_MODE_UNLINKED_ACTION_NAMES,
)
KEYMOUSE_FISHING_MODE_LINKS = _build_mode_links(
    KEYMOUSE_ACTIONS,
    FISHING_MODE_PREFIX,
    {},
    FISHING_MODE_UNLINKED_ACTION_NAMES,
)


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

        # ゲームパッド用のUI状態
        self.combo_vars: dict[str, tk.StringVar] = {}
        self.comboboxes: dict[str, ttk.Combobox] = {}
        self.action_helper_vars: dict[str, tk.StringVar] = {}
        self.action_helper_combos: dict[str, ttk.Combobox] = {}
        self.controller_action_control_widgets: dict[str, list[ttk.Combobox]] = {}

        # キーボード/マウス用のUI状態
        self.keymouse_combo_vars: dict[str, tk.StringVar] = {}
        self.keymouse_comboboxes: dict[str, ttk.Combobox] = {}
        self.keymouse_action_control_widgets: dict[str, list[ttk.Combobox]] = {}
        self._keymouse_custom_records: dict[str, tuple[int, int]] = {}

        self.controller_actions_by_name = {
            action["name"]: action
            for action in ACTIONS
        }
        self.keymouse_actions_by_name = {
            action["name"]: action
            for action in KEYMOUSE_ACTIONS
        }

        self.path_var = tk.StringVar()
        self.detected_save_var = tk.StringVar()
        self.detected_saves: list[tuple[str, Path]] = []
        self.status_var = tk.StringVar(value="ファイル未選択")
        self.base_status_message = "ファイル未選択"

        self.preset_var = tk.StringVar()
        self.helper1_var = tk.StringVar()
        self.helper2_var = tk.StringVar()
        self.controller_var = tk.StringVar(value=DEFAULT_CONTROLLER)
        self.keymouse_mode_var = tk.BooleanVar(value=False)
        self.controller_photo_mode_independent_var = tk.BooleanVar(value=False)
        self.keymouse_photo_mode_independent_var = tk.BooleanVar(value=False)
        self.keymouse_fishing_mode_independent_var = tk.BooleanVar(value=False)

        self.preset_combobox: Optional[ttk.Combobox] = None
        self.helper1_combobox: Optional[ttk.Combobox] = None
        self.helper2_combobox: Optional[ttk.Combobox] = None
        self.controller_combobox: Optional[ttk.Combobox] = None
        self.controller_mode_button: Optional[ttk.Button] = None
        self.keymouse_mode_button: Optional[ttk.Button] = None
        self.detected_save_combobox: Optional[ttk.Combobox] = None
        self.path_entry: Optional[ttk.Entry] = None
        self.rescan_button: Optional[ttk.Button] = None
        self.manual_select_button: Optional[ttk.Button] = None
        self.button_layout_load_button: Optional[ttk.Button] = None
        self.controller_photo_mode_checkbutton: Optional[ttk.Checkbutton] = None
        self.keymouse_photo_mode_checkbutton: Optional[ttk.Checkbutton] = None
        self.keymouse_fishing_mode_checkbutton: Optional[ttk.Checkbutton] = None

        self.keybind_group: Optional[ttk.LabelFrame] = None
        self.controller_action_group: Optional[ttk.LabelFrame] = None
        self.controller_photo_action_group: Optional[ttk.LabelFrame] = None
        self.keymouse_action_group: Optional[ttk.LabelFrame] = None
        self.keymouse_photo_action_group: Optional[ttk.LabelFrame] = None
        self.controller_fishing_action_group: Optional[ttk.LabelFrame] = None
        self.keymouse_fishing_action_group: Optional[ttk.LabelFrame] = None

        self.reset_button: Optional[ttk.Button] = None
        self.save_button: Optional[ttk.Button] = None

        self._suspend_events = False
        self._last_controller_type = DEFAULT_CONTROLLER
        self._last_helper1_display = ""
        self._last_helper2_display = ""
        self._combobox_dropdown_open = False
        self._active_dropdown_combo: Optional[ttk.Combobox] = None
        self._dropdown_watch_job = None

        self._build_ui()
        self._bind_traces()
        self._bind_mousewheel()
        self._bind_clear_selection_click()
        self._restore_mode_independent_settings_from_startup_json()
        self._update_mode_linking()
        self._update_input_mode_ui()
        self.rescan_detected_saves()
        self.update_save_button_state()

    def _get_program_dir(self) -> Path:
        """実行ファイルまたは.pyと同じフォルダを返す。"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    def get_button_layout_path(self) -> Path:
        return self._get_program_dir() / BUTTON_LAYOUT_FILE_NAME

    def _restore_mode_independent_settings_from_startup_json(self):
        """起動時に保存済みJSONからモード単独設定のチェック状態だけを復元する。"""
        path = self.get_button_layout_path()
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return

        if not isinstance(data, dict):
            return

        controller_profile = data.get("controller_profile")
        keymouse_profile = data.get("keymouse_profile")

        previous_suspend = self._suspend_events
        self._suspend_events = True
        try:
            if isinstance(controller_profile, dict):
                self.controller_photo_mode_independent_var.set(
                    controller_profile.get("photo_mode_independent") is True
                )

            if isinstance(keymouse_profile, dict):
                self.keymouse_photo_mode_independent_var.set(
                    keymouse_profile.get("photo_mode_independent") is True
                )
                self.keymouse_fishing_mode_independent_var.set(
                    keymouse_profile.get("fishing_mode_independent") is True
                )
        finally:
            self._suspend_events = previous_suspend

    def _append_combo_value_if_missing(self, combo: Optional[ttk.Combobox], label: str):
        if combo is None or not label:
            return
        current_values = list(combo["values"])
        if label not in current_values:
            current_values.append(label)
            combo["values"] = current_values

    def _append_keymouse_combo_value_if_missing(
        self,
        action_name: str,
        label: str,
        input_type: int,
        value: int,
    ):
        combo = self.keymouse_comboboxes.get(action_name)
        if combo is None or not label:
            return
        self._append_combo_value_if_missing(combo, label)
        self._keymouse_custom_records[label] = (input_type, value)

    def _collect_controller_layout_profile(self) -> dict:
        return {
            "controller_type": self._get_current_controller_type(),
            "photo_mode_independent": bool(
                self.controller_photo_mode_independent_var.get()
            ),
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

    def _collect_keymouse_layout_profile(self) -> dict:
        return {
            "photo_mode_independent": bool(
                self.keymouse_photo_mode_independent_var.get()
            ),
            "fishing_mode_independent": bool(
                self.keymouse_fishing_mode_independent_var.get()
            ),
            "actions": {
                action["name"]: {
                    "key": self.keymouse_combo_vars[action["name"]].get(),
                }
                for action in KEYMOUSE_ACTIONS
                if action["name"] in self.keymouse_combo_vars
            },
        }

    def _collect_button_layout(self) -> dict:
        return {
            "version": 4,
            "input_device": self._get_selected_input_device(),
            "controller_profile": self._collect_controller_layout_profile(),
            "keymouse_profile": self._collect_keymouse_layout_profile(),
        }

    def _write_button_layout_file(self) -> Path:
        """現在のUI上のキー設定をJSONへ保存し、保存先を返す。"""
        path = self.get_button_layout_path()
        data = self._collect_button_layout()
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _apply_controller_layout_profile(self, profile: dict, controller_type: str):
        if controller_type not in CONTROLLER_OPTIONS:
            controller_type = DEFAULT_CONTROLLER

        self.controller_var.set(controller_type)
        self._refresh_controller_dependent_labels()

        keybind = profile.get("keybind") or {}
        actions = profile.get("actions") or {}
        if not isinstance(keybind, dict) or not isinstance(actions, dict):
            raise ValueError("ゲームパッド配置の形式が不正です。")

        helper_values = list(self._get_helper_value_to_label().values())
        preset_values = [label for _, label in self._get_current_preset_options()]

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

        valid_button_labels = self._get_current_action_label_to_value()
        valid_helper_labels = set(self._get_action_helper_display_values())

        for action in ACTIONS:
            name = action["name"]
            saved = actions.get(name)
            if not isinstance(saved, dict):
                continue

            if self._controller_action_uses_helper(action):
                helper_label = saved.get("helper")
                if helper_label in valid_helper_labels:
                    self.action_helper_vars[name].set(helper_label)

            button_label = saved.get("button")
            if button_label in valid_button_labels:
                self._append_combo_value_if_missing(
                    self.comboboxes.get(name),
                    button_label,
                )
                self.combo_vars[name].set(button_label)

        self.controller_photo_mode_independent_var.set(
            bool(profile.get("photo_mode_independent", False))
        )
        self._refresh_action_combobox_choices()
        self._refresh_action_helper_combobox_choices()
        self._update_mode_linking()
        self._update_preset_editability()

    def _apply_keymouse_layout_profile(self, profile: dict):
        actions = profile.get("actions") or {}
        if not isinstance(actions, dict):
            raise ValueError("キーボード/マウス配置の形式が不正です。")

        for action in KEYMOUSE_ACTIONS:
            name = action["name"]
            saved = actions.get(name)
            if not isinstance(saved, dict):
                continue

            key_label = saved.get("key")
            if key_label in KEYMOUSE_LABEL_TO_RECORD:
                self.keymouse_combo_vars[name].set(key_label)

        self.keymouse_photo_mode_independent_var.set(
            bool(profile.get("photo_mode_independent", False))
        )
        self.keymouse_fishing_mode_independent_var.set(
            bool(profile.get("fishing_mode_independent", False))
        )
        self._update_mode_linking()

    def load_button_layout(self):
        """JSONからUI上の配置だけを読み込む。localsave.bytesには書かない。"""
        path = self.get_button_layout_path()
        if not path.exists():
            messagebox.showerror("配置読み込みエラー", f"配置ファイルが見つかりません。\n{path}")
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("配置ファイルの形式が不正です。")

            # version 1 の旧形式も、ゲームパッド配置として読み込めるようにする。
            if "controller_profile" in data:
                controller_profile = data.get("controller_profile") or {}
                keymouse_profile = data.get("keymouse_profile") or {}
                input_device = data.get("input_device") or DEFAULT_CONTROLLER
                controller_type = controller_profile.get("controller_type") or DEFAULT_CONTROLLER
            else:
                legacy_controller = data.get("controller")
                controller_type = (
                    legacy_controller
                    if legacy_controller in CONTROLLER_OPTIONS
                    else DEFAULT_CONTROLLER
                )
                controller_profile = {
                    "controller_type": controller_type,
                    "keybind": data.get("keybind") or {},
                    "actions": data.get("actions") or {},
                }
                keymouse_profile = {}
                input_device = controller_type

            if not isinstance(controller_profile, dict) or not isinstance(keymouse_profile, dict):
                raise ValueError("配置ファイルの形式が不正です。")

            if controller_type not in CONTROLLER_OPTIONS:
                controller_type = DEFAULT_CONTROLLER
            if input_device not in SAVED_INPUT_DEVICE_OPTIONS:
                input_device = controller_type

            self._suspend_events = True
            try:
                self._apply_controller_layout_profile(controller_profile, controller_type)
                self._apply_keymouse_layout_profile(keymouse_profile)
                self.keymouse_mode_var.set(input_device == KEYMOUSE_DEVICE)
                self._update_input_mode_ui()
            finally:
                self._suspend_events = False

            self.base_status_message = f"キー設定を読み込みました: {path.name}"
            self.update_save_button_state()
            messagebox.showinfo(
                "配置読み込み",
                "キー設定を読み込みました。\nゲーム設定へ反映するには、通常の保存ボタンを押してください。",
            )
        except Exception as ex:
            self.base_status_message = "キー設定の読み込みに失敗しました"
            self.update_save_button_state()
            messagebox.showerror("配置読み込みエラー", f"キー設定の読み込みに失敗しました。\n{ex}")

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        # スクロール全体
        self.canvas = tk.Canvas(main, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            main,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self._on_canvas_yview)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = ttk.Frame(self.canvas, padding=10)
        self.content.columnconfigure(0, weight=1)

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )

        self.content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width),
        )

        row = 0

        file_group = ttk.LabelFrame(
            self.content,
            text="設定ファイルを選択",
            padding=8,
        )
        file_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        file_group.columnconfigure(0, weight=1)
        row += 1

        detected_group = ttk.LabelFrame(
            self.content,
            text="検出された設定ファイル",
            padding=8,
        )
        detected_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        detected_group.columnconfigure(0, weight=1)
        row += 1

        layout_group = ttk.LabelFrame(
            self.content,
            text="キー設定プリセット",
            padding=8,
        )
        layout_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        layout_group.columnconfigure(0, weight=1)
        row += 1

        input_device_group = ttk.LabelFrame(
            self.content,
            text="入力デバイスを選択",
            padding=8,
        )
        input_device_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        input_device_group.columnconfigure(0, weight=1)
        row += 1

        self.keybind_group = ttk.LabelFrame(
            self.content,
            text="補助キー設定",
            padding=8,
        )
        self.keybind_group.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        self.keybind_group.columnconfigure(0, weight=1)
        row += 1

        action_group_row = row
        self.controller_action_group = ttk.LabelFrame(
            self.content,
            text="通常キー設定",
            padding=8,
        )
        self.controller_action_group.grid(
            row=action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.controller_action_group.columnconfigure(0, weight=1)

        self.keymouse_action_group = ttk.LabelFrame(
            self.content,
            text="通常キー設定",
            padding=8,
        )
        self.keymouse_action_group.grid(
            row=action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.keymouse_action_group.columnconfigure(0, weight=1)
        self.keymouse_action_group.grid_remove()
        row += 1

        photo_action_group_row = row
        self.controller_photo_action_group = ttk.LabelFrame(
            self.content,
            text="撮影モードのキー設定",
            padding=8,
        )
        self.controller_photo_action_group.grid(
            row=photo_action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.controller_photo_action_group.columnconfigure(0, weight=1)

        self.keymouse_photo_action_group = ttk.LabelFrame(
            self.content,
            text="撮影モードのキー設定",
            padding=8,
        )
        self.keymouse_photo_action_group.grid(
            row=photo_action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.keymouse_photo_action_group.columnconfigure(0, weight=1)
        self.keymouse_photo_action_group.grid_remove()
        row += 1

        fishing_action_group_row = row
        self.controller_fishing_action_group = ttk.LabelFrame(
            self.content,
            text="釣りモードのキー設定",
            padding=8,
        )
        self.controller_fishing_action_group.grid(
            row=fishing_action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.controller_fishing_action_group.columnconfigure(0, weight=1)

        self.keymouse_fishing_action_group = ttk.LabelFrame(
            self.content,
            text="釣りモードのキー設定",
            padding=8,
        )
        self.keymouse_fishing_action_group.grid(
            row=fishing_action_group_row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )
        self.keymouse_fishing_action_group.columnconfigure(0, weight=1)
        self.keymouse_fishing_action_group.grid_remove()
        row += 1

        # ファイル選択
        file_row = ttk.Frame(file_group)
        file_row.grid(row=0, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)

        self.path_entry = ttk.Entry(file_row, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.manual_select_button = ttk.Button(
            file_row,
            text="手動選択",
            command=self.select_file,
        )
        self.manual_select_button.grid(row=0, column=1, sticky="e")

        ttk.Label(
            file_group,
            text=(
                "キー設定の設定ファイルは通常、次の場所にあります。\n"
                "%USERPROFILE%\\AppData\\LocalLow\\bokura\\[アジア版やSteam版などのフォルダ]\\ \n"
                "localsave\\Env1\\[数字のフォルダ]\\[キャラクターUIDのフォルダ]\\localsave.bytes (2 KB以上)"
            ),
            justify="left",
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
        self.detected_save_combobox.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 10),
        )
        self.detected_save_combobox.bind(
            "<<ComboboxSelected>>",
            self._on_detected_save_selected,
        )
        self._register_combobox_bindings(self.detected_save_combobox)

        self.rescan_button = ttk.Button(
            detected_row,
            text="再スキャン",
            command=self.rescan_detected_saves,
        )
        self.rescan_button.grid(row=0, column=1, sticky="e")

        # 入力デバイス
        input_mode_button_row = ttk.Frame(input_device_group)
        input_mode_button_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        input_mode_button_row.columnconfigure(0, weight=1)
        input_mode_button_row.columnconfigure(1, weight=1)

        self.controller_mode_button = ttk.Button(
            input_mode_button_row,
            text="ゲームパッド",
            command=self._activate_controller_mode,
            state="disabled",
        )
        self.controller_mode_button.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 4),
        )

        self.keymouse_mode_button = ttk.Button(
            input_mode_button_row,
            text="キーボード/マウス",
            command=self._activate_keymouse_mode,
        )
        self.keymouse_mode_button.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(4, 0),
        )

        input_device_row = ttk.Frame(input_device_group)
        input_device_row.grid(row=1, column=0, sticky="ew")
        input_device_row.columnconfigure(0, weight=1)

        self.controller_combobox = ttk.Combobox(
            input_device_row,
            textvariable=self.controller_var,
            values=INPUT_DEVICE_OPTIONS,
            state="readonly",
            justify="left",
        )
        self.controller_combobox.grid(row=0, column=0, sticky="ew")
        self._register_combobox_bindings(self.controller_combobox)

        # キー設定プリセット
        layout_row = ttk.Frame(layout_group)
        layout_row.grid(row=0, column=0, sticky="ew")
        layout_row.columnconfigure(0, weight=1)

        ttk.Label(
            layout_row,
            text=f"保存先: {BUTTON_LAYOUT_FILE_NAME}",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        self.button_layout_load_button = ttk.Button(
            layout_row,
            text="読み込み",
            command=self.load_button_layout,
        )
        self.button_layout_load_button.grid(
            row=0,
            column=1,
            sticky="e",
        )

        # ゲームパッドの補助キー・確認/キャンセル
        helper_values = [
            self._get_helper_value_to_label()[value]
            for value, _ in HELPER_OPTIONS
        ]

        self.helper1_combobox = self._add_top_combo_row(
            parent=self.keybind_group,
            row=0,
            label="補助キー1",
            variable=self.helper1_var,
            values=list(helper_values),
            width=10,
        )

        self.helper2_combobox = self._add_top_combo_row(
            parent=self.keybind_group,
            row=1,
            label="補助キー2",
            variable=self.helper2_var,
            values=list(helper_values),
            width=10,
        )

        self.preset_combobox = self._add_top_combo_row(
            parent=self.keybind_group,
            row=2,
            label="確認/キャンセル",
            variable=self.preset_var,
            values=[label for _, label in self._get_current_preset_options()],
            width=10,
            pady=(0, 0),
        )

        # 通常のアクション一覧
        for action_row, action in enumerate(CONTROLLER_MAIN_ACTIONS):
            self._add_action_row(
                self.controller_action_group,
                action_row,
                action,
            )

        for action_row, action in enumerate(KEYMOUSE_MAIN_ACTIONS):
            self._add_keymouse_action_row(
                self.keymouse_action_group,
                action_row,
                action,
            )

        # 撮影モードのアクション一覧
        self.controller_photo_mode_checkbutton = ttk.Checkbutton(
            self.controller_photo_action_group,
            text="撮影モードのアクションを単独で設定する",
            variable=self.controller_photo_mode_independent_var,
        )
        self.controller_photo_mode_checkbutton.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )

        for action_row, action in enumerate(
            CONTROLLER_PHOTO_MODE_ACTIONS,
            start=1,
        ):
            self._add_action_row(
                self.controller_photo_action_group,
                action_row,
                action,
                display_name=action["name"].removeprefix(PHOTO_MODE_PREFIX),
            )

        self.keymouse_photo_mode_checkbutton = ttk.Checkbutton(
            self.keymouse_photo_action_group,
            text="撮影モードのアクションを単独で設定する",
            variable=self.keymouse_photo_mode_independent_var,
        )
        self.keymouse_photo_mode_checkbutton.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )

        for action_row, action in enumerate(
            KEYMOUSE_PHOTO_MODE_ACTIONS,
            start=1,
        ):
            self._add_keymouse_action_row(
                self.keymouse_photo_action_group,
                action_row,
                action,
                display_name=action["name"].removeprefix(PHOTO_MODE_PREFIX),
            )

        # 釣りモードのアクション一覧
        for action_row, action in enumerate(
            CONTROLLER_FISHING_MODE_ACTIONS,
        ):
            self._add_action_row(
                self.controller_fishing_action_group,
                action_row,
                action,
                display_name=action["name"].removeprefix(FISHING_MODE_PREFIX),
            )

        self.keymouse_fishing_mode_checkbutton = ttk.Checkbutton(
            self.keymouse_fishing_action_group,
            text="釣りモードのアクションを単独で設定する",
            variable=self.keymouse_fishing_mode_independent_var,
        )
        self.keymouse_fishing_mode_checkbutton.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )

        for action_row, action in enumerate(
            KEYMOUSE_FISHING_MODE_ACTIONS,
            start=1,
        ):
            self._add_keymouse_action_row(
                self.keymouse_fishing_action_group,
                action_row,
                action,
                display_name=action["name"].removeprefix(FISHING_MODE_PREFIX),
            )

        # フッター（固定）
        footer = ttk.Frame(self.root, padding=(10, 6, 10, 10))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(
            row=0,
            column=0,
            sticky="w",
        )

        button_frame = ttk.Frame(footer)
        button_frame.grid(row=0, column=1, sticky="e")

        self.save_button = ttk.Button(
            button_frame,
            text="保存",
            command=self.save_file,
            state="disabled",
        )
        self.save_button.pack(side="right")

        self.reset_button = ttk.Button(
            button_frame,
            text="リセット",
            command=self.reset_values,
            state="disabled",
        )
        self.reset_button.pack(side="right", padx=(0, 8))

        self.root.bind_class(
            "TCombobox",
            "<MouseWheel>",
            self._on_combobox_mousewheel,
        )

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

    def _add_action_row(
        self,
        parent: ttk.Frame,
        row: int,
        action: dict,
        display_name: Optional[str] = None,
    ):
        """ゲームパッド用のアクション行を追加する。"""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        frame.columnconfigure(0, weight=1)

        action_name = action["name"]
        uses_helper_ui = self._controller_action_uses_helper(action)

        ttk.Label(
            frame,
            text=display_name if display_name is not None else action_name,
        ).grid(row=0, column=0, sticky="w")

        helper_var = tk.StringVar(value=ACTION_HELPER_NONE_LABEL)
        var = tk.StringVar()
        controls: list[ttk.Combobox] = []

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

            ttk.Label(frame, text="+").grid(
                row=0,
                column=2,
                sticky="e",
                padx=(0, 4),
            )

            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=self._get_controller_action_display_values(action),
                state="readonly",
                width=10,
                justify="right",
            )
            combo.grid(row=0, column=3, sticky="e")

            self._register_combobox_bindings(helper_combo)
            self.action_helper_combos[action_name] = helper_combo
            controls.append(helper_combo)
        else:
            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=self._get_controller_action_display_values(action),
                state="readonly",
                width=10,
                justify="right",
            )
            combo.grid(row=0, column=1, columnspan=3, sticky="e")

        self._register_combobox_bindings(combo)
        controls.append(combo)

        self.action_helper_vars[action_name] = helper_var
        self.combo_vars[action_name] = var
        self.comboboxes[action_name] = combo
        self.controller_action_control_widgets[action_name] = controls

    def _get_keymouse_action_display_values(self, action: dict) -> list[str]:
        allowed_input_types = action.get("allowed_input_types")
        if not allowed_input_types:
            return list(KEYMOUSE_COMBO_VALUES)

        allowed_types = set(allowed_input_types)
        return [
            label
            for input_type, _value, label in KEYMOUSE_OPTIONS
            if input_type in allowed_types
        ]

    def _add_keymouse_action_row(
        self,
        parent: ttk.Frame,
        row: int,
        action: dict,
        display_name: Optional[str] = None,
    ):
        """キーボード/マウス用のアクション行を追加する。補助キーUIは持たない。"""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        frame.columnconfigure(0, weight=1)

        action_name = action["name"]
        ttk.Label(
            frame,
            text=display_name if display_name is not None else action_name,
        ).grid(row=0, column=0, sticky="w")

        var = tk.StringVar()
        combo_column = 1
        if action_name in KEYMOUSE_LCTRL_PREFIX_ACTION_NAMES:
            ttk.Label(frame, text="L Ctrl +").grid(
                row=0,
                column=1,
                sticky="e",
                padx=(0, 4),
            )
            combo_column = 2

        combo = ttk.Combobox(
            frame,
            textvariable=var,
            values=self._get_keymouse_action_display_values(action),
            state="readonly",
            width=14,
            justify="right",
        )
        combo.grid(row=0, column=combo_column, sticky="e")

        self._register_combobox_bindings(combo)
        self.keymouse_combo_vars[action_name] = var
        self.keymouse_comboboxes[action_name] = combo
        self.keymouse_action_control_widgets[action_name] = [combo]

    def _bind_traces(self):
        self.controller_var.trace_add("write", self._on_controller_changed)
        self.preset_var.trace_add("write", self._on_any_value_changed)
        self.helper1_var.trace_add("write", self._on_helper1_changed)
        self.helper2_var.trace_add("write", self._on_helper2_changed)
        self.controller_photo_mode_independent_var.trace_add(
            "write",
            self._on_any_value_changed,
        )
        self.keymouse_photo_mode_independent_var.trace_add(
            "write",
            self._on_any_value_changed,
        )
        self.keymouse_fishing_mode_independent_var.trace_add(
            "write",
            self._on_any_value_changed,
        )

        for var in self.combo_vars.values():
            var.trace_add("write", self._on_any_value_changed)

        for var in self.action_helper_vars.values():
            var.trace_add("write", self._on_any_value_changed)

        for var in self.keymouse_combo_vars.values():
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
            *self.keymouse_comboboxes.values(),
        ]

        for combo in combo_list:
            if combo is None or not combo.winfo_exists():
                continue
            try:
                combo.selection_clear()
            except tk.TclError:
                pass

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

    def _get_selected_input_device(self) -> str:
        if self._is_keymouse_mode():
            return KEYMOUSE_DEVICE
        return self._get_current_controller_type()

    def _activate_controller_mode(self):
        self._set_input_mode(keymouse_mode=False)

    def _activate_keymouse_mode(self):
        self._set_input_mode(keymouse_mode=True)

    def _set_input_mode(self, keymouse_mode: bool):
        previous_suspend = self._suspend_events
        self._suspend_events = True
        try:
            self.keymouse_mode_var.set(keymouse_mode)
            self._update_input_mode_ui()
            self._update_mode_linking()
        finally:
            self._suspend_events = previous_suspend

        if not previous_suspend:
            self.update_save_button_state()

    def _is_keymouse_mode(self) -> bool:
        return bool(self.keymouse_mode_var.get())

    def _get_current_controller_type(self) -> str:
        selected = self.controller_var.get()
        if selected in CONTROLLER_OPTIONS:
            return selected
        if self._last_controller_type in CONTROLLER_OPTIONS:
            return self._last_controller_type
        return DEFAULT_CONTROLLER

    def _update_input_mode_ui(self):
        """選択中の入力デバイスに合わせて、表示する配置UIを切り替える。"""
        if (
            self.keybind_group is None
            or self.controller_action_group is None
            or self.controller_photo_action_group is None
            or self.controller_fishing_action_group is None
            or self.keymouse_action_group is None
            or self.keymouse_photo_action_group is None
            or self.keymouse_fishing_action_group is None
        ):
            return

        if self._is_keymouse_mode():
            self.keybind_group.grid_remove()
            self.controller_action_group.grid_remove()
            self.controller_photo_action_group.grid_remove()
            self.controller_fishing_action_group.grid_remove()
            self.keymouse_action_group.grid()
            self.keymouse_photo_action_group.grid()
            self.keymouse_fishing_action_group.grid()

            if self.controller_mode_button is not None:
                self.controller_mode_button.configure(state="normal")
            if self.keymouse_mode_button is not None:
                self.keymouse_mode_button.configure(state="disabled")
            if self.controller_combobox is not None:
                self.controller_combobox.configure(state="disabled")
        else:
            self.keymouse_action_group.grid_remove()
            self.keymouse_photo_action_group.grid_remove()
            self.keymouse_fishing_action_group.grid_remove()
            self.keybind_group.grid()
            self.controller_action_group.grid()
            self.controller_photo_action_group.grid()
            self.controller_fishing_action_group.grid()

            if self.controller_mode_button is not None:
                self.controller_mode_button.configure(state="disabled")
            if self.keymouse_mode_button is not None:
                self.keymouse_mode_button.configure(state="normal")
            if self.controller_combobox is not None:
                self.controller_combobox.configure(state="readonly")


    def _set_controller_action_controls_enabled(
        self,
        action_name: str,
        enabled: bool,
    ):
        state = "readonly" if enabled else "disabled"
        for combo in self.controller_action_control_widgets.get(action_name, []):
            combo.configure(state=state)

    def _set_keymouse_action_controls_enabled(
        self,
        action_name: str,
        enabled: bool,
    ):
        state = "readonly" if enabled else "disabled"
        for combo in self.keymouse_action_control_widgets.get(action_name, []):
            combo.configure(state=state)

    def _sync_controller_mode_linking(
        self,
        mode_actions: list[dict],
        mode_links: dict[str, str],
        independent: bool,
    ):
        previous_suspend = self._suspend_events
        self._suspend_events = True
        try:
            for action in mode_actions:
                mode_name = action["name"]
                source_name = mode_links.get(mode_name)
                is_linked = source_name in self.combo_vars

                if not independent and is_linked:
                    self.combo_vars[mode_name].set(
                        self.combo_vars[source_name].get()
                    )

                    if (
                        self._controller_action_uses_helper(action)
                        and source_name in self.action_helper_vars
                    ):
                        self.action_helper_vars[mode_name].set(
                            self.action_helper_vars[source_name].get()
                        )

                self._set_controller_action_controls_enabled(
                    mode_name,
                    independent or not is_linked,
                )
        finally:
            self._suspend_events = previous_suspend

    def _sync_keymouse_mode_linking(
        self,
        mode_actions: list[dict],
        mode_links: dict[str, str],
        independent: bool,
    ):
        previous_suspend = self._suspend_events
        self._suspend_events = True
        try:
            for action in mode_actions:
                mode_name = action["name"]
                source_name = mode_links.get(mode_name)
                is_linked = source_name in self.keymouse_combo_vars

                if not independent and is_linked:
                    self.keymouse_combo_vars[mode_name].set(
                        self.keymouse_combo_vars[source_name].get()
                    )

                self._set_keymouse_action_controls_enabled(
                    mode_name,
                    independent or not is_linked,
                )
        finally:
            self._suspend_events = previous_suspend

    def _update_mode_linking(self):
        self._sync_controller_mode_linking(
            CONTROLLER_PHOTO_MODE_ACTIONS,
            CONTROLLER_PHOTO_MODE_LINKS,
            bool(self.controller_photo_mode_independent_var.get()),
        )
        self._sync_keymouse_mode_linking(
            KEYMOUSE_PHOTO_MODE_ACTIONS,
            KEYMOUSE_PHOTO_MODE_LINKS,
            bool(self.keymouse_photo_mode_independent_var.get()),
        )
        self._sync_controller_mode_linking(
            CONTROLLER_FISHING_MODE_ACTIONS,
            CONTROLLER_FISHING_MODE_LINKS,
            True,
        )
        self._sync_keymouse_mode_linking(
            KEYMOUSE_FISHING_MODE_ACTIONS,
            KEYMOUSE_FISHING_MODE_LINKS,
            bool(self.keymouse_fishing_mode_independent_var.get()),
        )

    def get_input_offsets(self, action: dict, dec: Optional[bytes] = None) -> list[int]:
        """
        ゲームパッド側のBKRInputConfigData相対value位置を返す。

        UU1では一部だけキーボード/マウスと並びが入れ替わるため、
        lodef位置とUU1候補のどちらが controller record かをtypeで判定する。
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
        if resolved:
            return resolved

        return [self.input_anchor_pos + rel for rel in action["rel_offsets"]]

    def get_keymouse_input_offsets(self, action: dict, dec: Optional[bytes] = None) -> list[int]:
        """
        キーボード/マウス側のBKRInputConfigData相対value位置を返す。

        type=0x01/0x02のレコードだけを採用するため、UU1の入れ替わり位置も
        lodef / UU1のどちらかへ自動追従する。
        """
        if self.input_anchor_pos is None:
            raise ValueError("入力設定が読み込まれていません。")

        rel_candidates = list(action["rel_offsets"])
        for rel in ACTION_KEYMOUSE_OFFSET_ALIASES.get(action["name"], []):
            if rel not in rel_candidates:
                rel_candidates.append(rel)

        abs_candidates = [self.input_anchor_pos + rel for rel in rel_candidates]

        if dec is None:
            return abs_candidates

        resolved = [
            off for off in abs_candidates
            if self._is_keymouse_action_record(dec, off)
        ]
        if resolved:
            return resolved

        return [self.input_anchor_pos + rel for rel in action["rel_offsets"]]

    def _is_standard_action_record(self, dec: bytes, off: int) -> bool:
        """
        controller側のアクションレコードか判定する。

        構造:
          off - 0x04 = type
          off + 0x00 = value
          off + 0x04 = state
          off + 0x08 = third dword

        third dwordは撮影モードの方向入力などで0以外になるため、
        判定には使わず保存時も変更しない。
        """
        if off < 4 or off + 8 > len(dec):
            return False

        input_type = int.from_bytes(dec[off - 4:off], "little")
        state_dword = int.from_bytes(dec[off + 4:off + 8], "little")

        return (
            input_type == INPUT_TYPE_CONTROLLER
            and state_dword in (
                ACTION_STATE_SINGLE,
                ACTION_STATE_HELPER1,
                ACTION_STATE_HELPER2,
            )
        )

    def _is_keymouse_action_record(self, dec: bytes, off: int) -> bool:
        if off < 4 or off + 4 > len(dec):
            return False

        input_type = int.from_bytes(dec[off - 4:off], "little")
        return input_type in (INPUT_TYPE_KEYBOARD, INPUT_TYPE_MOUSE)

    def get_writable_input_offsets(self, action: dict, dec: bytes) -> list[int]:
        return [
            off
            for off in self.get_input_offsets(action, dec)
            if self._is_standard_action_record(dec, off)
        ]

    def get_writable_keymouse_offsets(self, action: dict, dec: bytes) -> list[int]:
        return [
            off
            for off in self.get_keymouse_input_offsets(action, dec)
            if self._is_keymouse_action_record(dec, off)
        ]

    def _controller_action_uses_helper(self, action: dict) -> bool:
        if "uses_helper" in action:
            return bool(action["uses_helper"])
        return action["name"] not in SPECIAL_ACTIONS_WITHOUT_HELPER

    def _get_controller_action_allowed_values(self, action: dict) -> list[int]:
        if "allowed_values" in action:
            return list(action["allowed_values"])
        return list(CONTROLLER_ASSIGNABLE_VALUES)

    def _get_controller_action_display_values(
        self,
        action: dict,
        exclude_blocked: bool = False,
    ) -> list[str]:
        value_to_label = self._get_current_action_value_to_label()
        allowed_values = self._get_controller_action_allowed_values(action)

        if exclude_blocked and "allowed_values" not in action:
            blocked_values = self._get_blocked_action_values()
            if self._controller_action_uses_helper(action):
                allowed_values = [
                    value for value in allowed_values
                    if value not in blocked_values
                ]

        return [
            value_to_label[value]
            for value in allowed_values
            if value in value_to_label
        ]

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
        controller = self._get_current_controller_type()
        return CONTROLLER_DISPLAY_MAPS.get(
            controller,
            CONTROLLER_DISPLAY_MAPS[DEFAULT_CONTROLLER],
        )

    def _get_current_action_label_to_value(self) -> dict[str, int]:
        value_to_label = self._get_current_action_value_to_label()
        return {label: value for value, label in value_to_label.items()}

    def _get_current_preset_options(self) -> list[tuple[int, str]]:
        controller = self._get_current_controller_type()
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
        """ゲームパッド用の各アクションに、許可されたボタン候補を反映する。"""
        for action in ACTIONS:
            name = action["name"]
            combo = self.comboboxes.get(name)
            var = self.combo_vars.get(name)
            if combo is None or var is None:
                continue

            current = var.get()
            values = self._get_controller_action_display_values(
                action,
                exclude_blocked=True,
            )
            if current and current not in values:
                values.append(current)
            combo["values"] = values

        self._update_mode_linking()

    def _refresh_controller_dependent_labels(self):
        old_controller = self._last_controller_type
        new_controller = self._get_current_controller_type()

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
        self._update_mode_linking()
        if not self._preset_supported:
            self.preset_var.set(self._get_default_preset_label())
        self._update_preset_editability()
        self._last_controller_type = new_controller

    def _on_any_value_changed(self, *args):
        if self._suspend_events:
            return

        self._update_mode_linking()
        self.update_save_button_state()

    def _clear_conflicts_for_helper_value(self, helper_main_value: int, other_helper: str):
        action_value = HELPER_MAIN_TO_ACTION_VALUE.get(helper_main_value)
        if action_value is None:
            return

        action_label_to_value = self._get_current_action_label_to_value()
        helper_label_to_value = self._get_helper_label_to_value()

        for action in ACTIONS:
            name = action["name"]
            if not self._controller_action_uses_helper(action):
                continue

            var = self.combo_vars.get(name)
            if var is None:
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
            self._update_input_mode_ui()
            self._update_mode_linking()
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
            self._update_mode_linking()
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
            self._update_mode_linking()
        finally:
            self._suspend_events = False

        self.update_save_button_state()

    def has_blank_required_fields(self) -> bool:
        if self.file_path is None:
            return True

        if self._is_keymouse_mode():
            return any(not var.get() for var in self.keymouse_combo_vars.values())

        if not self.helper1_var.get():
            return True
        if not self.helper2_var.get():
            return True
        if not self.preset_var.get():
            return True

        return any(not var.get() for var in self.combo_vars.values())

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
                    if off < 4 or off + 8 > len(dec):
                        raise ValueError("ファイルの形式が想定と異なります。")

            for action in KEYMOUSE_ACTIONS:
                for off in self.get_keymouse_input_offsets(action):
                    if off < 4 or off + 4 > len(dec):
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
                self._update_input_mode_ui()
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

    def _load_controller_values_from_dec(self, dec: bytes):
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

            if not self._controller_action_uses_helper(action):
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

    def _load_keymouse_values_from_dec(self, dec: bytes):
        for action in KEYMOUSE_ACTIONS:
            name = action["name"]
            offsets = self.get_keymouse_input_offsets(action, dec)
            first_off = offsets[0]

            input_type = int.from_bytes(dec[first_off - 4:first_off], "little")
            value = int.from_bytes(dec[first_off:first_off + 4], "little")
            label = KEYMOUSE_RECORD_TO_LABEL.get((input_type, value))

            if label is None:
                label = f"不明 (type=0x{input_type:08X}, value=0x{value:08X})"
                self._append_keymouse_combo_value_if_missing(
                    name,
                    label,
                    input_type,
                    value,
                )

            self.keymouse_combo_vars[name].set(label)

    def _load_values_from_dec(self, dec: bytes):
        self._load_controller_values_from_dec(dec)
        self._load_keymouse_values_from_dec(dec)
        self._update_mode_linking()

    def reset_values(self):
        if self.original_dec is None:
            return

        self._suspend_events = True
        try:
            self._load_values_from_dec(self.original_dec)
            self._refresh_action_combobox_choices()
            self._refresh_action_helper_combobox_choices()
            self._update_preset_editability()
            self._update_input_mode_ui()
        finally:
            self._suspend_events = False

        self.base_status_message = "読み込み時の状態に戻しました"
        self.update_save_button_state()

    def _commit_saved_dec(self, dec: bytearray):
        if self.file_path is None:
            raise ValueError("設定ファイルが選択されていません。")

        enc = brotli.compress(bytes(dec), quality=1)
        self.file_path.write_bytes(enc)
        self.original_dec = bytes(dec)

        self._suspend_events = True
        try:
            self._load_values_from_dec(self.original_dec)
            self._refresh_action_combobox_choices()
            self._refresh_action_helper_combobox_choices()
            self._update_preset_editability()
            self._update_input_mode_ui()
        finally:
            self._suspend_events = False

    def _save_controller_file(self):
        if self.original_dec is None:
            raise ValueError("設定ファイルが読み込まれていません。")

        self._update_mode_linking()
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

            if self._controller_action_uses_helper(action):
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

        self._commit_saved_dec(dec)

    def _save_keymouse_file(self):
        if self.original_dec is None:
            raise ValueError("設定ファイルが読み込まれていません。")

        self._update_mode_linking()
        dec = bytearray(self.original_dec)

        for action in KEYMOUSE_ACTIONS:
            name = action["name"]
            selected_label = self.keymouse_combo_vars[name].get()

            record = KEYMOUSE_LABEL_TO_RECORD.get(selected_label)
            if record is None:
                record = self._keymouse_custom_records.get(selected_label)
            if record is None:
                raise ValueError(f"{name} のキーが不正です。")

            input_type, value = record
            for off in self.get_writable_keymouse_offsets(action, self.original_dec):
                dec[off - 4:off] = input_type.to_bytes(4, "little")
                dec[off:off + 4] = value.to_bytes(4, "little")

        self._commit_saved_dec(dec)

    def save_file(self):
        if self.file_path is None or self.original_dec is None:
            return

        if self.has_blank_required_fields():
            self.update_save_button_state()
            return

        try:
            if self._is_keymouse_mode():
                self._save_keymouse_file()
            else:
                self._save_controller_file()

            preset_path = self._write_button_layout_file()

            self.base_status_message = "保存しました"
            self.update_save_button_state()
            messagebox.showinfo(
                "保存完了",
                f"保存しました。\nキー設定プリセットを作成しました。\n{preset_path}",
            )

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