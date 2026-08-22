# agents-scaffold

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | 日本語

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI コーディングエージェントはルールを破ります。お願いするのではなく、コミットを止めます。**

コマンド 1 回で `.claude/` 構成と pre-commit ゲートがリポジトリに入ります。フレームワークも
ランタイムも、接続するレジストリもありません — 手に入るのは**完全にあなたのものである普通のファイル**です。

![デモ: ワンコマンドのブートストラップ、生成された .claude/ ツリー、ステージングされた .env をブロックする pre-commit ゲート](docs/assets/demo.gif)

_30秒デモ: コマンド1つ → 記入済みの `.claude/` → ゲートがシークレットのコミットをブロック。`vhs docs/assets/demo.tape` で再現できます。_

## こんな覚えがあるなら、これです

- 同じルールを**セッションのたびに説明し直している** — 昨日伝えたことを今日はもう知らない。
- エージェントが `.env` をステージした。型エラーが残ったままコミットが作られた。
- メンバーごとに `CLAUDE.md` がばらばらで、**誰のセッションかで結果が変わる。**

ドキュメントに書いただけのルールは、AI がいずれ無視します。このスキャフォールドはルールを
**コミットを止めるゲート**に変えて、リポジトリに埋め込みます。

## Quickstart

```bash
# クローン不要、コマンド1つで
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# またはローカルクローンから(オプション省略時は対話的にプロンプト)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

記入済みの `.claude/` ディレクトリ(エージェント、スキル、フック、paths スコープの
ルール、メモリ)、プロジェクトの頭脳となる `AGENTS.md`、そして合成された単一の pre-commit
ゲートが手に入ります — すべて完全にあなたが所有するプレーンなファイルです。全オプションは
[Usage](docs/OPTIONS.ja.md#usage-1--script) を参照してください。

## インストール直後に起きること

エージェント(あるいは人)がシークレットをコミットしようとすると、**コミット自体が通りません。**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

ドキュメントに「シークレットをコミットしないこと」と書くのとは違います。止めているのは
`.git/hooks/pre-commit` なので、**どの AI ツールを使っても、人が手でコミットしても同じように掛かります。**

## 何が手に入るか — 初心者向け

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="コマンド1つ → 自分が所有する .claude/(エージェント、スキル、コマンド、ルール、フック、メモリ、AGENTS.md)→ ステージングされた .env・壊れたビルド・lint 失敗をブロックする強制ゲート" src="docs/assets/overview-light.svg">
</picture>

インストールの1分後には、Claude はルールを心得たチームメイトのように振る舞います。
プロンプトに不慣れでも大丈夫です:

- **ワークフローがデフォルトになる**: 「ログイン機能を作って」と言えば、Claude が
  イシュー → ブランチ → 実装 → テスト → PR/MR を自律的に進めます(`/fix-issue`;
  `/sdlc-cycle` は役割分離された3つのエージェントで無人サイクルを実行)。
- **ミスは機構でブロックされる**: `.env`/シークレットのコミット、壊れたビルドや
  型エラー、新規 JSP スクリプトレットは pre-commit フックが止め、
  複雑度 15 を超える関数にはフラグが立ちます — Claude が忘れても捕捉するゲートです。
- **ワンショットコマンド**: `/review`(コードレビュー + セキュリティ監査)、`/status`、
  `/knowledge-graph`(ドキュメントリンクチェッカー)、`/sonar`。
- **要件の鍛え込みは 3 つから選択**: 同梱の **`grill-me`** に加えて、用途に応じて外部ツール
  2 つを組み合わせられます → [要件を鍛えるツールの選び方](docs/OPTIONS.ja.md#要件を鍛えるツールの選び方)。
- **セッションをまたいで生き残るメモリ**: プロジェクトの学びが
  `.claude/memory/` 配下に蓄積され、次のセッションで自動ロードされ、チームで共有されます。
- **自己進化**: skill-evolve/agent-evolve が失敗のフィードバックからスキル/エージェント
  定義を書き換えます — 使えば使うほど良くなります。
- **チーム/マルチセッションでも安全**: セッションごとの git worktree 分離が
  デフォルトなので、並行作業が互いを踏み荒らすことはありません。

## なぜ agents-scaffold か

大規模なインストール型フレームワークやエージェント/スキルのカタログと違い、agents-scaffold は
ランタイムも、プラグインシステムも、同期を保つべき中央レジストリも持ちません —
これは `.claude/` ディレクトリのスケルトンと少数のスタックプリセットであり、
一度リポジトリにコピーしたらあとは完全にあなたのものです。後からアップグレードすべきものは
何もありません: フォークし、プレースホルダーを埋め、不要なものを削除すれば、
結果はリポジトリ内の他のコードと同じくバージョン管理下のプレーンなファイルです。

- **建前ではなく強制** — P0/P1/P2 階層はフック(pre-commit ゲート、deny ルール、
  CC 警告)に配線されており、散文で書かれているだけではありません。
- **paths スコープのルール** — ルールはマッチするファイルを触っている間だけロードされるため、
  すべての規約を先頭ロードせずコンテキストがスリムに保たれます。
- **自己改善** — `skill-evolve`/`agent-evolve` が実際のミスから「Learned warnings」を
  スキルとエージェントに追記します。
- **テスト済み** — ブートストラップスクリプトには bats のリグレッションスイートが同梱され、
  knowledge-graph リンクチェッカーがドキュメントをゲートします。

## さらに詳しく

| ドキュメント | 内容 |
|---|---|
| [docs/OPTIONS.ja.md](docs/OPTIONS.ja.md) | 全オプション — スタックプリセット 10 種、`--forge`、`--harness`、`--lang`、使い方、プレースホルダー置換、要件を鍛えるツールの選び方 |
| [docs/INTERNALS.ja.md](docs/INTERNALS.ja.md) | 内部構造 — 生成される `.claude/` の全ツリー、主要パターン |
| [CONTRIBUTING.md](CONTRIBUTING.md) | コントリビュートガイド |

## コントリビュート

ワークフローは [CONTRIBUTING.md](CONTRIBUTING.md)、スタックプリセットの形式は
[docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) を参照してください。
初めての方は [`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) から始めるのがおすすめです —
レイアウトが完全にテンプレート化されているため、新しいスタックプリセットの追加が最も取り組みやすい課題です。

## ライセンス

MIT — [LICENSE](LICENSE) を参照してください。サードパーティ由来（スキル・ドキュメント）は [CREDITS.md](CREDITS.md) に記載しています。
