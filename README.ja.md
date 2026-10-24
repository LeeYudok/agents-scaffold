# agents-scaffold

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh.md) | 日本語

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

**AI コーディングエージェント(Claude Code・Codex・Antigravity)のためのガードレール。実際の git pre-commit ゲートで強制します。**

AI コーディングエージェントはルールを破ります。お願いするのではなく、コミットを止めます。
コマンド 1 回で、プロジェクトの頭脳となる `AGENTS.md`、paths スコープのルール、スキル、サブエージェント、フック、
合成された pre-commit ゲートがリポジトリに入ります。フレームワークもランタイムもレジストリもありません — **完全にあなたのものである普通のファイル**です。

![デモ: ワンコマンドのブートストラップ、生成された .claude/ ツリー、ステージングされた .env をブロックする pre-commit ゲート](docs/assets/demo.gif)

_30秒デモ: コマンド1つ → 記入済みの `.claude/` → ゲートがシークレットのコミットをブロック。`vhs docs/assets/demo.tape` で再現できます。_

## こんな覚えがあるなら、これです

- 同じルールを**セッションのたびに説明し直している** — 昨日伝えたことを今日はもう知らない。
- エージェントが `.env` をステージした。型エラーが残ったままコミットが作られた。
- メンバーごとに `CLAUDE.md` がばらばらで、**誰のセッションかで結果が変わる。**
- チームで Claude Code・Codex・Antigravity が混在していて、**全員に共通のルールを 1 セット**にしたい。
- **閉域網や Windows** で作業しているが、大半のエージェント設定はそのどちらも想定していない。

ドキュメントにしかないルールは、いずれ無視されます。このスキャフォールドはルールを
**コミットを止めるゲート**に変えて、リポジトリに埋め込みます。

## Quickstart

```bash
# one command, no clone required
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# or from a local clone (prompts interactively when options are omitted)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app

# Codex or Antigravity too: --harness codex | agy | all
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --harness all --stack python --yes
```

インストール済みなら、`--update` がベースファイルを更新し、あなたが変更したファイルの横には `<file>.new` を書き出すので、
編集内容が上書きされることはありません。全オプション: [docs/OPTIONS.ja.md](docs/OPTIONS.ja.md#usage-1--script)。

## なぜ機能するのか

| 強み | 意味 |
|---|---|
| **プロンプトではなく git で強制** | `.git/hooks/pre-commit` が、ステージングされた `.env`/シークレット、壊れたビルド、型エラー・lint エラーをブロックします。どの AI ツールを使っても、人が手でコミットしても同じように掛かります。 |
| **ソースは 1 つ、エージェントは 3 つ** | `AGENTS.md` が単一の真実の源(SSOT)で、Claude Code・Codex・Antigravity のすべてがネイティブに読みます。スキルは `.agents/skills/` に一度だけ置き、Codex のサブエージェント(`.codex/agents/*.toml`)と Antigravity のルール・サブエージェント・フックは `.claude/` から生成します。 |
| **想定ではなく実測** | ハーネスに関する主張はすべて [docs/harness-matrix.json](docs/harness-matrix.json) の実測で裏付けられています — Claude Code と Antigravity は **full** ティア、Codex は **baseline**。実測の有効期限が切れると CI が失敗します。 |
| **スタックプリセット 12 種** | Next.js、Spring Boot、Java web(JSP)、Bun、Python、Go、Rust、Ruby on Rails、.NET、Android、Flutter、ops — それぞれがルールと独自の build/lint/test ゲートを追加します。forge は GitHub か GitLab、出力は韓国語か英語。 |
| **paths スコープのルール** | ルールはエージェントがマッチするファイルを触っている間だけロードされるため、すべての規約を先頭ロードせずコンテキストがスリムに保たれます。 |
| **すぐ使えるスキル 24 個** | ワークフロー(review、status、handoff、docs-sync、セキュリティ事前点検 など)に加え、`yd-*` 専門スキル: PostgreSQL、Oracle、SQLite、リレーショナル設計、Go、React、TypeScript、Vite/pnpm ビルド、モバイル画面設計、そして**依存関係の CVE 点検**(オンラインは `pnpm audit`、オフラインは OSV ダンプ)。 |
| **閉域網と Windows に対応** | オフラインバンドルはネットワークなしでインストールでき、Windows は Git Bash と `.cmd` ランチャーで動きます([docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md))。 |
| **プラグインマーケットプレイス** | スキルは Claude Code / Codex のプラグインとしてグローバルにもインストールできます — クローン不要。 |
| **自己改善** | `skill-evolve` / `agent-evolve` が実際のミスを、それを起こしたスキルやエージェントの「Learned warnings」に変えます。 |
| **テスト済み** | インストーラーの bats リグレッションテスト 89 個、スキルごとの契約テスト、ドキュメントのリンクチェッカー。すべて CI で実行。 |

## インストール直後に起きること

エージェント(あるいは人)がシークレットをコミットしようとすると、**コミット自体が通りません。**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

ドキュメントに「シークレットをコミットしないこと」と書くのとは違います。止めているのは git フックです。

## 何が手に入るか

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="コマンド1つ → 自分が所有する .claude/(エージェント、スキル、コマンド、ルール、フック、メモリ、AGENTS.md)→ ステージングされた .env・壊れたビルド・lint 失敗をブロックする強制ゲート" src="docs/assets/overview-light.svg">
</picture>

インストールの1分後には、エージェントはルールを心得たチームメイトのように振る舞います — プロンプトに不慣れでも大丈夫です:

- **ワークフローがデフォルトになる**: 「ログイン機能を作って」と言えば、エージェントが
  イシュー → ブランチ → 実装 → テスト → PR/MR を自律的に進めます(`/fix-issue`;
  `/sdlc-cycle` は役割分離された3つのエージェントで無人サイクルを実行)。
- **ミスは機構でブロックされる**: `.env`/シークレットのコミット、壊れたビルドや型エラー、新規 JSP
  スクリプトレットは pre-commit フックが止め、認知的複雑度 15 を超える関数にはフラグが立ちます。
- **階層化されたルール**: P0(絶対 — シークレット、破壊的 SQL、force push)、P1(必須 — イシュー連携、テスト)、
  P2(推奨)— `AGENTS.md` に一度だけ書き、ツールで強制できるところは強制します。
- **ワンショットコマンド**: `/review`(コードレビュー + セキュリティ監査)、`/status`、`/knowledge-graph`
  (ドキュメントリンクチェッカー)、`/sonar`。
- **要件の鍛え込みは 3 つから選択**: 同梱の **`grill-me`**、または用途に応じて外部ツール 2 つ
  → [要件を鍛えるツールの選び方](docs/OPTIONS.ja.md#要件を鍛えるツールの選び方)。
- **セッションをまたいで生き残るメモリ**: プロジェクトの学びが `.claude/memory/` 配下に蓄積され、
  次のセッションで自動ロードされ、チームで共有されます。
- **チーム/マルチセッションでも安全**: セッションごとの git worktree 分離がデフォルトなので、
  並行するエージェントが互いの作業を踏み荒らすことはありません。

## スキル

デフォルトのインストールにはスキル 24 個が入ります: ワークフロースキル 10 個と、`yd-*` 専門スキル 14 個(データベース、Go、React、
TypeScript、ビルド、画面設計、韓国語ライティング、依存関係の CVE 点検)。メンテナーの環境に依存する `yd-*` 9 個は
`--with-personal-skills` を付けたときだけインストールされます。`yd-*` スキルは韓国語で書かれています。
一覧と作成規約は [.claude/skills/README.md](.claude/skills/README.md) にあります。

**スキルをプラグインとしてグローバルにインストール。** Claude Code と Codex は同じ `.claude-plugin/marketplace.json` を読みます:

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

`yd-skills` には `yd-*` 14 個と `handoff`・`docs-sync`・`memory-factcheck`・`skill-evolve` が、
`yd-skills-personal` にはオプトイン 9 個が入っています。Claude Code ではプラグインのスキルに名前空間が付きます(`yd-skills:yd-pg-expert`)。
プラグインが運ぶのはスキルだけです — Claude Code のプラグインは rules を、Codex のプラグインはサブエージェントを運べないため、
プロジェクトのルール・フック・サブエージェントはインストーラーから入れます。各プラグインには Antigravity 用マニフェスト
(`.antigravity-plugin/plugin.json`)もありますが、agy のドキュメントを基に作成したもので未実測です。オフラインや開発用途では、
このリポジトリを clone して `scripts/install-skills.sh` を実行します(`~/.claude/skills`・`~/.agents/skills`・
`~/.gemini/config/skills` にシンボリックリンク。`--personal`・`--copy`・`--project <dir>` に対応)。

## 比較

| | 手書きの `CLAUDE.md` | インストール型エージェントフレームワーク | agents-scaffold |
|---|---|---|---|
| ルールが実際に強制される | いいえ — エージェントが無視しうる | 多くはエージェントのランタイム内 | はい — git フック + CI、どのエージェントの外側でも |
| Claude Code・Codex・Antigravity で動く | いいえ | 多くは 1 ベンダーのみ | はい — `AGENTS.md` + 生成されるアダプター |
| インストールしてアップグレードし続けるもの | なし | ランタイムや CLI | なし — リポジトリ内のプレーンなファイル |
| オフライン/閉域網インストール | 該当なし | まれ | はい — オフラインバンドル |

## さらに詳しく

| ドキュメント | 内容 |
|---|---|
| [docs/OPTIONS.ja.md](docs/OPTIONS.ja.md) | 全オプション — スタックプリセット 12 種、`--forge`、`--harness`、`--lang`、`--update`、`--with-personal-skills`、プレースホルダー置換 |
| [docs/INTERNALS.ja.md](docs/INTERNALS.ja.md) | 内部構造 — 生成される全ツリー、リポジトリ構成、主要パターン |
| [docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md) | 閉域網・Windows インストール — オフラインバンドル、Git Bash、`.cmd` ランチャー、`python3` 設定(英語) |
| [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) | スタックプリセットの形式(韓国語) |
| [dotfiles/](dotfiles/README.md) | メンテナーのマシン用シェル環境(zsh、starship、Claude/Codex/agy ステータスライン)。scaffold のインストールとは別物(韓国語) |

## コントリビュート

ワークフローは [CONTRIBUTING.md](CONTRIBUTING.md)、スタックプリセットの形式は
[docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) を参照してください。初めての方は
[`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) から始めるのがおすすめです —
レイアウトが完全にテンプレート化されているため、新しいスタックプリセットの追加が最も取り組みやすい課題です。

## ライセンス

MIT — [LICENSE](LICENSE) を参照してください。サードパーティ由来(スキル・ドキュメント)は [CREDITS.md](CREDITS.md) と
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) に記載しています。
