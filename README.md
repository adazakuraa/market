# market-dashboard（個人用 日本株・経済ダッシュボード）

スマホから見る前提の、日本株セクター分析・ニュース・天気・電車遅延をまとめた個人用サイト。
GitHub Actionsで1日1〜2回自動更新し、GitHub Pagesで表示する。

## 仕組み
1. GitHub Actionsが定期実行（cron）される
2. Pythonスクリプトが yfinance / JPX公開データ / 気象庁データ / RSS等を取得
3. 取得データから指標を計算し、`docs/` フォルダにHTMLを生成
4. `docs/` の中身がGitHub Pagesとしてそのまま公開される
5. スマホのブラウザでそのURLを開けば見られる

## フェーズ
- **Phase 1（今回作成分）**: セクター強度ランキング（東証33業種のTOPIX比・相対強度）
- Phase 2: 銘柄スクリーニング（ゴールデンクロス候補、ADX/OBV/RSI/MACD、押し目、ATRポジションサイズ）
- Phase 3: ニュース（キーワードフィルタ）
- Phase 4: 天気・地震・電車遅延

## セットアップ手順（Phase 1）
1. このリポジトリ一式をGitHubにアップロード（フォルダ構成を保ったまま）
2. リポジトリの `Settings → Pages` で、Source を `Deploy from a branch`、Branch を `main` / フォルダを `/docs` に設定
3. リポジトリの `Settings → Actions → General` で「Read and write permissions」を有効化（Actionsがdocsフォルダにコミットするため）
4. `Actions` タブから `update-dashboard` ワークフローを手動実行（Run workflow）
5. 数分後、`https://<あなたのユーザー名>.github.io/<リポジトリ名>/` が表示されればOK

## 注意点
- yfinanceはYahoo Financeの非公式データ取得ライブラリです。個人の非商用利用を想定していますが、Yahoo側の仕様変更で動かなくなる可能性があります。動かなくなった場合は知らせてください、代替方法に切り替えます。
- 銘柄ユニバースは「JPX上場銘柄一覧」の規模コードで、TOPIX Core30・Large70・Mid400（＝おおよそ中〜大型株、TOPIX500相当）に絞っています。
