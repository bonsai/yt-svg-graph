# MIXUE video project

約2分の日本語解説動画。PNGストーリーボード経路を主経路、HTML/SVG経路を互換用の legacy 経路として扱います。

## Project layout

```text
01-mixue/
├── assets/                 # 入力素材（storyboard.png）
├── config/                 # tts.json、requirements.txt、panel-map.example.json
├── docs/                   # このREADME、pipeline.puml、actions.recap.md
├── scripts/
│   ├── pipeline/           # TTS、パネル検出・切り出し、QA、mux
│   └── legacy/             # 旧HTML/SVG動画経路
├── html/                   # HTML/SVGソース
├── tools/                  # ローカル用ツール（配布可能な生成物は置かない）
└── build/                  # 全生成物。Git管理外
    ├── video/              # mixue.mp4
    ├── audio/              # narration.wav / narration.mp3
    ├── panels/             # 原寸パネル画像（QA/VLM入力）
    ├── frames/             # 16:9表示フレーム
    ├── normalized/         # 等幅・同高の確認用画像
    ├── inspect/             # 境界検出の比較ギャラリー
    ├── tts/                # TTSキャッシュと音声クリップ
    ├── manifest.json       # パネル座標・シーン対応
    ├── panel-map.json      # シーン→パネル対応（手動設定）
    ├── qa.json              # 機械QAとVLM判定
    ├── timing.json          # 実測音声タイミング
    └── mux-report.json      # 音声・映像長の検証結果
```

## PNG pipeline

```bash
cd 01-mixue
pip install -r config/requirements.txt
python scripts/pipeline/make-tts.py
python scripts/pipeline/png2mov.py --prepare-only
# LM Studio のローカルVLMを利用する場合
python scripts/pipeline/qa_vlm.py --force
# QAの結果を確認してから最終動画を作成
python scripts/pipeline/png2mov.py --allow-review
```

## Output contract

- `build/panels/` は原寸の切り出し。QA/VLMの入力として保持します。
- `build/frames/` は動画表示用の16:9フレームです。元パネルを切り落とさない `contain` を基本にします。
- `build/manifest.json`, `build/qa.json`, `build/timing.json`, `build/mux-report.json` が検証可能なメタデータです。
- `build/` は生成物専用で、ソース素材や手動設定を保存しません。
- VLMの確認では、シーン意味対応だけでなく、各切り出しの境界・隣接コマの混入・内容の欠落も確認します。

## HTML/SVG legacy route

`scripts/legacy/` と `html/` にあります。PNG経路と混在させず、必要な場合のみ使います。

## CI

GitHub Actions の **Build video assets** がTTSとパネル準備・機械QAを実行し、成果物をArtifactsに保存します。YouTubeへの自動アップロードはしません。

> Note: workflow のQAパスとArtifact globも、最新のフラットな `build/` 契約と照合して更新する必要があります。大規模なフォルダ移動は、それらの参照を一括更新する変更として別段階で実施します。
