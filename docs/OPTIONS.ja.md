# agents-scaffold — 全オプション

`bin/agents-scaffold.sh` の全オプション。概要は [README](../README.ja.md) を参照。

## スタックプリセット

| プリセット | ルールファイル | pre-commit ゲート |
|--------|-----------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `./gradlew build` |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant compile (自動検出) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check` + `mypy` |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

## Forge プリセット (`--forge`)

利用する forge のイシュー/PR ワークフローを注入します。スタックプリセットより先にマージされます。

| プリセット | CLI | PR/MR | イシュークローズ |
|--------|-----|-------|-------------|
| `github` (デフォルト) | `gh` | PR | `Closes #N` によりマージ時に**自動クローズ** |
| `gitlab` | `glab` | MR | `Closes #N` の自動クローズは動作する — マージ後に確認し、open のままの場合のみ手動 |

注入されるファイル: `.claude/rules/forge.md`(常時ロード)に加え、
`.claude/commands/fix-issue.md` と `sdlc-cycle.md` の forge 別バリアント(ベースを上書き)。
ベースファイルは forge 非依存のまま("issue / PR·MR")です。

## 要件を鍛えるツールの選び方

実装前に要件を鍛える手段は 3 つあり、**性格が異なるのでタスクごとに選びます**。同梱されるのは `grill-me` だけで、残る 2 つは別途インストールします。

| | `grill-me` | superpowers | Ouroboros |
|---|---|---|---|
| **範囲** | 尋問のみ | ワークフロー全般 | 尋問 → 仕様 → 実行 → 評価のループ |
| **状態** | 会話の中で完結 | 会話 + ファイル成果物 | MCP サーバーが永続管理 |
| **重さ** | 軽い | 中 | 重い — 質問ごとにサブエージェントを fanout |
| **導入** | **同梱**(`.claude/skills/grill-me/`) | プラグイン [obra/superpowers](https://github.com/obra/superpowers) | マーケットプレイス [Q00/ouroboros](https://github.com/Q00/ouroboros)(MCP サーバー同梱) |

**選ぶ基準**

- 方向性が決まった機能の仕様に穴がないか調べたい → **`grill-me`**。インストール不要、会話 1 回で終わります。
- 白紙のアイデアを発散・収束させ、成果物(ドキュメント)も残したい → **superpowers の `brainstorming`**。
- 要件が曖昧な大きめの作業を**仕様化し、実行と評価までループで回したい** → **Ouroboros**。セッションが切れても状態は残りますが、トークンコストは 3 つの中で最大です。

重さの順に上げていき、**下から上へだけ**動かします — 軽い手段で足りる作業に Ouroboros を使ってもコストが増えるだけです。3 つとも入っていても自動では発動せず、タスクごとに使う側が選びます。

## ハーネス (`--harness`)

| 値 | 対象 | 動作 |
|---|---|---|
| `claude`（デフォルト） | Claude Code | フルインストール — settings.json のフックバインディング・サブエージェント・スラッシュコマンド・workflows を含む |
| `codex` | Codex ほか AGENTS.md 対応ハーネス | ハーネス中立の層（AGENTS.md・rules・skills・hooks・memory）のみ導入し、Claude 専用層を除去 |
| `all` | 混在チーム | フルインストール |

**保証レベルは 2 段階です（#21）** — 「対応している/していない」の二分法ではありません。

| レベル | 成立する内容 | 対象ハーネス |
|---|---|---|
| **baseline** | `AGENTS.md` 本文の P0/P1（選択したスタックの P0 を含む）+ **実際の `.git/hooks/pre-commit` ゲート** + CI | **`--harness` の値に関係なく全ハーネス。** ハーネスが何を読むかによらず、人が端末から直接コミットしても同じように掛かります |
| **full** | baseline + そのハーネスのネイティブ層（サブエージェント・skills・スラッシュコマンド・パススコープのルール読み込み・lifecycle フック） | アダプタが実測検証されたハーネスのみ |

git フックは**ハーネスに関係なく常に配線されます**（#21）。Claude Code の `PreToolUse` フックはそのセッションが Bash ツールでコミットしたときにのみ発火するため、早期フィードバック層であって強制線ではありません — 決定的な強制線はハーネスの外（`.git/hooks` + CI）に置きます。既存の `.git/hooks/pre-commit` は上書きせず、警告のみ出します。

選択したスタックの P0 は **`AGENTS.md` 本文に直接挿入**されます。`.claude/rules/` の参照リンクに依存しないため、`.claude/` を読み込まないハーネスでも到達可能です。選択していないスタックは挿入されません（Codex の指示合計はデフォルト 32KiB 上限 — context flooding を防ぐため）。

### 実測検証（2026-08-22）

| ハーネス | 実測バージョン | baseline | full 層で確認できたこと / できていないこと |
|---|---|---|---|
| Claude Code | 2.1.239 | 成立 | `.claude/rules/*.md` の `paths:` 条件付きロード、サブエージェント、skills、`settings.json` フック — いずれも[公式ドキュメント](https://code.claude.com/docs/en/memory.md)で確認 |
| Codex | codex-cli 0.149.0 | 成立 | `AGENTS.md` の自動ロードと P0 を根拠にした `.env` 拒否を実測。**skills は発見されない**（下記） |
| Antigravity | agy **1.1.18**（再測定なし） | 成立 | 1.1.17 で **headless（`-p`）がルールを読み込まない**ことを実測 — 原因は未解明。1.1.18 もインタラクティブモードも未検証 |

Codex（codex-cli 0.149.0）は `codex` モード成果物の AGENTS.md を自動で読み込み、ルール階層を正しく回答し、`.env` をコミットせよという指示を **P0 ルールを根拠に自ら拒否**しました（第一の防衛線）。モデルが強行しても git フックが exit 2 でブロックします（第二の防衛線、テスト済み）。

サポート状況の単一の真実の源は [`docs/harness-matrix.json`](harness-matrix.json) です。この表はその manifest と突き合わされ、CI では `scripts/check-harness-matrix.py` が検査します — `full` 等級が 90 日以上再実測されていない、あるいは判定に根拠がない場合、**ビルドは失敗します**。再実測は `scripts/spike-codex-contract.sh --dynamic` で行います。

**既知のギャップ — Codex の skills は自動発見されません。** Codex がリポジトリの skills を探す場所は `.agents/skills` ですが、現在の `--harness codex` は `.claude/skills` に残します。ルール層（`AGENTS.md`）は機能しますが skills 層は機能しません — これは full ではなく baseline です。

Codex 側の制約がもう 2 点、設計に効いてきます。

- **指示の合計はデフォルト 32KiB 上限**（`project_doc_max_bytes`）。そのため選択したスタックの P0 のみを `AGENTS.md` にインライン化します（`--stack javaweb` で実測 6,869 B — 上限の 21%）。
- **`.codex/` レイヤは信頼済みプロジェクトでのみロードされます。** ファイルを生成しても有効化は保証されません。だからこそ決定的な強制線は `.git/hooks` + CI に置きます。

## 言語 (`--lang`)

ベースツリー(エージェント、ルール、スキル、コマンド、`AGENTS.md`、フック/settings の
メッセージ)は**デフォルトで韓国語**です(#36 での反転 — 韓国語が単一の真実源で、
英語は翻訳オーバーレイ)。`--lang en` は英訳を最後に重ねます — ベースコピー、
forge プリセット、スタックプリセットの後に適用されるため、同じファイルを
`presets/lang-en/base` + `presets/lang-en/forge-<forge>` + `presets/lang-en/stacks/<stack>`
の内容で上書きします。

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`.claude/hooks/pre-commit.sh` は `--lang` によるオーバーレイの対象外です
(スタックパーシャルが挿入されるファイルであり、メッセージは単一言語、コードは
言語の影響を受けません)。`--update` は韓国語のベースのみを更新します。英語
オーバーレイを再適用したい場合は、その上で `--lang en` を付けて再実行してください。

## Usage 1 — script

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge のデフォルトは github。GitLab リポジトリには --forge gitlab を使う
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

`--forge`/`--stack`/`--name` を省略すると対話モードで実行され、スクリプトが
プロンプトを表示します(forge のデフォルトは github)。

### オプション

| オプション | 説明 |
|---|---|
| `<target-dir>` | 対象ディレクトリ。デフォルト `.` |
| `--forge <forge>` | `github`(デフォルト)または `gitlab` |
| `--lang <lang>` | `ko`(デフォルト)または `en` |
| `--stack <list>` | カンマ区切りのスタックプリセット。省略時は対話的にプロンプト |
| `--name <name>` | `{{PROJECT_NAME}}` の置換値。デフォルトは対象ディレクトリ名 |
| `--yes` | 対話プロンプトをスキップ(非対話モード) |
| `--update` | ブートストラップ済みプロジェクトのベースファイルを更新(後述) |

### リモートワンコマンドインストール(クローン不要)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

スクリプトはローカルチェックアウトから実行されていないこと(パイプ実行など)を検知すると、
`AGENTS_SCAFFOLD_REPO` の tarball(デフォルト: `github.com/leeyudok/agents-scaffold`、
環境変数で上書き可)を一時ディレクトリにダウンロードし、テンプレートソースとして
使用します。ブランチ/タグの固定は `AGENTS_SCAFFOLD_REF`(デフォルト `main`)で行います。

### ベースの更新 — `--update`

ブートストラップ済みプロジェクトに最新のベースファイル(`.claude/`、`AGENTS.md`、
`CLAUDE.md`、`GEMINI.md`)を適用します。

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
```

- `.claude/hooks/pre-commit.sh` は常にスキップされます — スタックパーシャルが
  挿入済みのため、手動マージが必要です。
- その他のベースファイルは、内容が同一ならスキップされます。差分がある場合は
  既存ファイルを保持し、新バージョンを `<file>.new` として書き出します
  (プレースホルダー置換は `.new` ファイルにも適用されます)。
- 最後に追加 / 更新保留 / スキップ / 変更なしのファイルのサマリーが出力されます —
  `.new` ファイルを `diff` で確認し、手動で適用してください。

## Usage 2 — GitLab テンプレート

新規プロジェクト作成時にこの設定を自動適用するには、
**[docs/GITLAB_TEMPLATE.md](GITLAB_TEMPLATE.md)** を参照してください。

> 注: このワークフローはセルフホストの GitLab インスタンスを前提とします。**GitLab CE** では
> ネイティブのカスタムプロジェクトテンプレートは Premium 機能のため利用できません —
> 代わりに **Import by URL + `bin/agents-scaffold.sh`**、または**スクリプト単体**を使ってください。
> 作成/インポート後に `bin/agents-scaffold.sh .` を1回実行すると、選択したスタックの適用、
> プレースホルダー置換、`bin/`/`presets/`/`docs/superpowers/` のセルフクリーンが行われます。

## プレースホルダー置換

| トークン | 値 |
|---|---|
| `{{PROJECT_NAME}}` | `--name` の値、または対象ディレクトリ名 |
| `{{JAVA_VERSION}}` | `1.8`(springboot プリセットのデフォルト) |
