# 01 · MIXUE

約2分の日本語解説動画。ストーリーボードPNG経路とHTML/SVG経路を分離しています。

## ディレクトリ構成

```
01-mixue/
├── assets/              # 入力アセット
│   └── storyboard.png   # ストーリーボード原画（3x3 = 9コマ）
├── config/              # 設定ファイル
│   ├── tts.json         # シーン定義（テキスト、声、タイミングヒント）
│   ├── requirements.txt # Python依存
│   └── panel-map.example.json
├── docs/                # ドキュメント
│   ├── README.md
│   ├── pipeline.puml    # PlantUMLフロー図
│   └── actions.recap.md
├── scripts/
│   ├── pipeline/        # メインパイプライン（実行順）
│   │   ├── make-tts.py          # 1. TTS生成・実測timing.json
│   │   ├── png2mov.py           # 2/4. パネル切り出し・QA・mux
│   │   ├── panel_grid.py        #   ガター検出・フィット共通ロジック
│   │   ├── panel_qa.py          # 3. 機械的QA（境界・重なり・比率）
│   │   ├── qa_vlm.py            #   VLM意味QA（cut/bleed/completeness）
│   │   ├── normalize_panels.py  #   等幅・同高プレビュー生成
│   │   └── inspect-panels.py    #   境界比較ギャラリー
│   └── legacy/        # 旧HTML/SVG経路
│       ├── build-video.py
│       ├── divide-img.py
│       ├── svg2mov.py
│       └── mux.py
├── html/                # HTML/SVG経路アセット
│   ├── index.html
│   ├── mixue_svg_2min.html
│   └── svg/
├── tools/               # 外部ツール
│   └── plantuml.jar
└── build/               # 生成物（.gitignore対象）
    ├── assets/          # 完成品・表示用
    │   ├── video/mixue.mp4
    │   ├── audio/narration.wav, narration.mp3
    │   ├── panels/      # 原寸切り出し（QA/VLM入力）
    │   ├── frames/      # 16:9表示フレーム
    │   └── diagrams/pipeline.svg
    ├── source/          # 中間データ・メタデータ
    │   ├── manifest/panel-manifest.json, panel-map.json
    │   ├── qa/panel-crop-qa.json, panel-crop-vlm.json
    │   ├── timing/timing.json
    │   ├── mux-report.json, png-scenes.txt
    ├── tts/             # TTS中間生成物
    │   ├── cache.json
    │   ├── voice/voice_XX.mp3
    │   └── voice-wav/voice_XX.wav
    └── panel/           # 検証用プレビュー
        ├── normalized/  # 等幅・同高（640x360 fill）
        └── inspect/     # 等分割vs検出境界の比較
```

## PNG経路（メイン）

```bash
cd 01-mixue

# 1. TTS生成 → 実測音声長で timing.json
python scripts/pipeline/make-tts.py

# 2. パネル切り出し + 機械QA → manifest, qa.json
python scripts/pipeline/png2mov.py --prepare-only

# 3. VLM意味QA（ローカルLM Studio必須） → vlm.json
python scripts/pipeline/qa_vlm.py

# 4. 最終mux（QA/VLM pass時のみ） → assets/video/mixue.mp4
python scripts/pipeline/png2mov.py --allow-review
```

### 主な設計

| 項目 | 内容 |
|------|------|
| **ガター検出** | 白行/列を検出しコマ境界を決定。失敗時のみ等分割フォールバック |
| **切り出しと表示の分離** | `assets/panels/` = 原寸（QA/VLM用）、`assets/frames/` = 16:9 contain |
| **音声ロック** | tts.jsonのstart/end不使用。生成音声の実測長から表示区間を決定 |
| **QAゲート** | 機械QA failなら停止。VLM verdict欠落/古い場合も既定で停止（`--allow-unverified`で回避可） |
| **正規化プレビュー** | mux時に `panel/normalized/` 生成（等幅・同高、fill/cover/contain切替可） |

### 成果物一覧

| パス | 内容 |
|------|------|
| `build/source/timing/timing.json` | 実測音声のシーン開始/終了・表示区間 |
| `build/source/manifest/panel-manifest.json` | コマ座標・原寸・表示fit・ハッシュ・シーン情報 |
| `build/source/qa/panel-crop-qa.json` | 機械検証 verdict と理由 |
| `build/source/qa/panel-crop-vlm.json` | VLMの cut/bleed/completeness 判定 |
| `build/source/manifest/panel-map.json` | シーン → コマの意味対応（手動作成） |
| `build/source/mux-report.json` | 音声・映像の実測長とドリフト |
| `build/panel/inspect/` | 等分割と境界検出の比較ギャラリー |

## HTML/SVG経路（legacy）

`scripts/legacy/` 以下参照。ストーリーボードPNGが無い場合のフォールバックとして残しています。

## CI / Build

GitHub Actions **Build video assets** を実行します。CIでは TTS → パネル切り出し → 機械QA までを行い、VLM判定と本描画はローカル（GPU必須）で実行想定です。成果物は Artifacts から取得可能。YouTube自動アップロードはしません。

## 依存

- Python 3.12+
- `pip install -r config/requirements.txt`（edge-tts, playwright, pillow, numpy）
- FFmpeg
- LM Studio（ローカルVLM用、tempura-qwen2.5-vl-3b 等）
- PlantUML + Java（図生成用、CI内蔵）