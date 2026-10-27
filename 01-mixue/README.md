# 01 · MIXUE

約2分の日本語解説動画。ストーリーボードPNG経路とHTML/SVG経路を分離しています。

## 現在のPNG経路

1. `make-tts.py` — シーンごとに日本語TTSを生成し、**実測した音声長**で `build/timing.json` を作る
2. `png2mov.py --prepare-only` — 9コマを切り出し、`build/panel-manifest.json` と `build/panel-crop-qa.json` を作る
3. `qa_vlm.py` — ローカルVLM（LM Studio）で切り出し内容を判定（pass / review / fail）
4. `png2mov.py` — QAとVLM verdictが通ったときだけ、音声タイミングに合わせてMP4を生成・muxする

```bash
cd 01-mixue
python make-tts.py
python png2mov.py --prepare-only
python qa_vlm.py                    # ローカルLM Studioが必要
python png2mov.py                   # build/mixue.mp4
```

### 独自の点

- **等分割しない**: 白ガターを行ごとに検出してコマ境界を決める（`panel_grid.py`）。検出に失敗した場合だけ等分割にフォールバックし、その事実をマニフェストとQAに残す
- **切り出しと表示を分離**: `build/png-panels/` は原寸のままVLM/QA用。`build/frames/` は16:9へcontain（余白パディング、内容を切らない）
- **音声が正**: `tts.json` の `start`/`end` は使わず、生成した音声の実測長から表示区間を決める。差分は `build/mux-report.json` に記録し、±0.12秒を超えたら失敗
- **QAゲート**: 機械検証（座標・ガター・欠け・比率・上書き検知）が `fail` なら描画しない。VLM verdictが無い/古い場合も既定では描画しない（`--allow-unverified` はプレビュー用）
- **等幅・同高プレビュー**: mux時に `build/normalized/` を生成。元の切り出しと動画フレームは変更しない

### 成果物

| ファイル | 内容 |
| --- | --- |
| `build/timing.json` | 実測音声のシーン開始/終了・表示区間 |
| `build/panel-manifest.json` | コマの座標・原寸・表示fit・ハッシュ・シーン情報 |
| `build/panel-crop-qa.json` | 機械検証の verdict と理由 |
| `build/panel-crop-vlm.json` | ローカルVLMの cut/bleed/completeness 判定 |
| `build/panel-map.json` | シーン → コマの意味対応（別工程） |
| `build/mux-report.json` | 音声・映像の実測長とドリフト |
| `build/inspect/` | 等分割と境界検出の比較ギャラリー |

### その他のファイル

- `index.html` / `svg2mov.py` / `divide-img.py` / `mux.py` — HTML/SVG経路
- `normalize_panels.py` — 等幅・同高のプレビュー生成（単体でも実行可）
- `inspect-panels.py` — 切り出し確認用ギャラリー
- `build-video.py` — 経路ルーター（autoはストーリーボードPNGを優先）

## Build

GitHub Actions の **Build video assets** を実行します。CIはTTS・切り出し・機械QAまでを行い、VLM判定と本描画はローカルで行う想定です。成果物はArtifactsから取得できます。YouTubeへの自動アップロードはしません。

PNGの数値は報道時点や集計方法に差があるため概数として表示し、価格比較は同一商品同士の比較ではないことを画面内に注記します。
