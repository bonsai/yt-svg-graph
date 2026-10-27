# 01 · MIXUE

約2分の日本語解説動画。ストーリーボードPNGを分割する経路と、HTML/SVGを描画する経路を分離しています。

## 素材と変換経路
- `MIXUE世界展開ストーリーボード展開.png` — PNG入力。既定では3列×3行に分割（9コマすべてを素材化）し、`tts.json` のシーン順・秒数に合わせてMP4化
- `index.html` — 16:9 HTML/SVGアニメーションの描画元
- `png2mov.py` — PNGストーリーボードを3×3の9コマに分割し、マニフェストを出力。ローカルVLMの対応付け後に動画化
- `build/panel-manifest.json` — 9コマと8シーンの入力情報。ローカルVLMの判定対象
- `build/panel-map.json` — VLMが作成する `scene_id` と `panel_id` の対応表。形式例は `panel-map.example.json`
- `svg2mov.py` — HTML/SVGをPlaywrightでフレーム化して動画化
- `build-video.py` — 内部ルーター。autoはストーリーボードPNGがあればPNG経路、なければSVG経路
- `tts.json` / `make-tts.py` — シーンごとの原稿と仮の日本語TTS
- `divide-img.py` / `mux.py` — SVG経路のフレーム分割と動画・音声結合

## Build
GitHub Actions の **Build video assets** を実行します。source は `auto` / `png` / `svg` から選択できます。成果物はArtifactsからダウンロードできます。YouTubeへ自動アップロードはしません。

PNG経路は既定で3列×3行として9コマすべてを `build/png-panels/` に保存し、`build/panel-manifest.json` を生成します。画像とナレーションシーンの意味的な対応は自動で決めず、ローカルVLMで判定して `build/panel-map.json` を作成してください。その後 `python png2mov.py` を実行すると、対応表に従ってMP4を生成します。素材だけを準備する場合は `python png2mov.py --prepare-only`。GitHub ActionsのPNG経路も判定を行わず、素材・マニフェスト・ナレーションをArtifactにまとめます。
数値は報道時点や集計方法に差があるため概数として表示し、価格比較は同一商品同士の比較ではないことを画面内に注記します。
