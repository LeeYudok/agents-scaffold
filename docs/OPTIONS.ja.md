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
| `codex` | Codex | `AGENTS.md`、skills、共有 rules/hooks/memory を導入し、`.codex/agents` TOML（#64）と `.codex/hooks.json`（#65）を生成、Claude 専用層（commands・workflows）を除去 |
| `agy` | Antigravity | `codex` の共通レイアウトに加え、`.claude/` から `.agents/rules`（`trigger: glob`、#63）・`.agents/agents`（#64）・`.agents/hooks.json`（#65）を生成 |
| `all` | 混在チーム | `claude` の全内容 + すべてのアダプタ（agy ルール、Codex・agy のサブエージェントとフック）。skills のレイアウトはハーネスに依存しない（#61） |

**skills の原本は 1 か所です（#61）。** ハーネスに関係なく skills は `.agents/skills/`（Codex・agy のネイティブパス）に 1 回だけ置き、Claude Code はシンボリックリンク `.claude/skills -> ../.agents/skills` 経由で同じファイルを読みます（claude 2.1.289 で実測 — リンクなしで `.agents/skills` だけを置くと Claude Code は skills を見つけられません）。2 つのコピーが食い違うことはなくなり、後から別のハーネスを加えても再インストールは不要です。

- シンボリックリンクを作れない環境（Windows Git Bash の既定値など）や `AGENTS_SCAFFOLD_NO_SYMLINK=1` の場合、`.claude/skills` はコピーになります。ステージされたコピーが原本と異なると pre-commit ゲートがコミットをブロックします（インデックス基準の比較なので `__pycache__` などの未追跡ファイルは対象外）。リンクを作れるかは環境によって変わりえます（ネットワーク分離 PC のポリシーなど）— [OFFLINE_INSTALL.en.md](OFFLINE_INSTALL.en.md) のステップ 6 を参照。
- Git for Windows で `core.symlinks=false` のままチェックアウトすると、リンクはパス文字列を含む通常ファイルになります。このとき Claude Code は skills を見つけられず、ゲートが警告を出します — `git config core.symlinks true` の後に再チェックアウトしてください。
- インストール前から実ディレクトリの `.claude/skills` がある場合は `.agents/skills` へ移してリンクにします。同じパスの内容が `.agents/skills` と異なる場合は `.agents/skills` を原本とし、元のディレクトリを `.claude/skills.pre-ssot-<時刻>/` に残します。
- ルールとサブエージェントはリンクしません。`.codex/rules` はコマンド実行ポリシー、agy の `.agents/rules` は Claude の `paths:` 条件付きロードを解釈せず、Claude の `.md` と Codex の `.toml` サブエージェントは形式が異なります。代わりにインストールと `--update` 時に各ハーネスの形式で生成します（#63、#64）。

3 つのハーネスはいずれもルートの `AGENTS.md` をネイティブに読むため、`CLAUDE.md`/`GEMINI.md` のポインタも `.gemini/settings.json` のシムも生成しません（#54、#60）。サポート対象は最新版の Claude Code・Codex・Antigravity で、Gemini CLI は対象から外しました。

**保証レベルは 2 段階です（#21）** — 「対応している/していない」の二分法ではありません。

| レベル | 成立する内容 | 対象ハーネス |
|---|---|---|
| **baseline** | `AGENTS.md` 本文の P0/P1（選択したスタックの P0 を含む）+ **実際の `.git/hooks/pre-commit` ゲート** + CI | **`--harness` の値に関係なく全ハーネス。** ハーネスが何を読むかによらず、人が端末から直接コミットしても同じように掛かります |
| **full** | baseline + そのハーネスのネイティブ層（サブエージェント・skills・スラッシュコマンド・パススコープのルール読み込み・lifecycle フック） | アダプタが実測検証されたハーネスのみ |

git フックは**ハーネスに関係なく常に配線されます**（#21）。Claude Code の `PreToolUse` フックはそのセッションが Bash ツールでコミットしたときにのみ発火するため、早期フィードバック層であって強制線ではありません — 決定的な強制線はハーネスの外（`.git/hooks` + CI）に置きます。既存の `.git/hooks/pre-commit` は上書きせず、警告のみ出します。

選択したスタックの P0 は **`AGENTS.md` 本文に直接挿入**されます。`.claude/rules/` の参照リンクに依存しないため、`.claude/` を読み込まないハーネスでも到達可能です。選択していないスタックは挿入されません（Codex の指示合計はデフォルト 32KiB 上限 — context flooding を防ぐため）。

### 実測検証（2026-10-04）

| ハーネス | 実測バージョン | baseline | full 層で確認できたこと / できていないこと |
|---|---|---|---|
| Claude Code | 2.1.289 | 成立 | `.claude/rules/*.md` の `paths:` 条件付きロード、サブエージェント、skills、`settings.json` フック — いずれも[公式ドキュメント](https://code.claude.com/docs/en/memory.md)で確認 |
| Codex | codex-cli 0.160.0 / GPT-6.1 Sol | 成立 | `AGENTS.md`、インラインのスタック P0、`.agents/skills`、`.env` ゲート、`.codex/agents` サブエージェント（信頼済みプロジェクトのみ）、`.codex/hooks.json` フック（プロジェクトとフック定義の信頼が必要）、cwd 基準のサブディレクトリ `AGENTS.md` を実測。ファイルパス条件付きの指示はない |
| Antigravity | agy 1.2.16 | 成立 | headless（`-p`）で `AGENTS.md`、インラインのスタック P0、`.agents/skills`、`.env` ゲート、`.agents/agents` サブエージェント、`.agents/hooks.json` フック（信頼確認なしで実行）、`.agents/rules` の `trigger: glob` 条件付きルールを実測。サブディレクトリの `AGENTS.md` は cwd 基準でのみ読み込まれる |

Codex（codex-cli 0.160.0、`gpt-6.1-sol`）と agy（1.2.16）は、各モード成果物の AGENTS.md とインラインのスタック P0 をツール呼び出しなしで自動的に読み込み、`.agents/skills` のリポジトリ skills のみを発見しました。どちらも `.claude/skills` は発見しません。agy 1.2.7 の headless は `AGENTS.md` も `GEMINI.md` も読み込めませんでしたが、1.2.16 で解消されています。モデルがルールを見落としても git フックが staged `.env` を exit 2 でブロックします。

サポート状況の単一の真実の源は [`docs/harness-matrix.json`](harness-matrix.json) です。この表はその manifest と突き合わされ、CI では `scripts/check-harness-matrix.py` が検査します — `full` 等級が 90 日以上再実測されていない、あるいは判定に根拠がない場合、**ビルドは失敗します**。再実測は `scripts/spike-codex-contract.sh --dynamic` と `scripts/spike-agy-contract.sh --dynamic` で行います。

**agy ルールアダプタ（#63）。** `--harness agy|all` では `.claude/rules/*.md` を `.agents/rules/*.md` として生成します。`paths:` があれば `trigger: glob` + `globs:`、なければ `trigger: always_on` になります。パターンは agy 1.2.16 の実測どおりに変換します — スラッシュを含む相対パターン（`src/**`）は `**/src/**` に、スラッシュのないパターン（`Dockerfile`・`*.py`）はファイル名に一致するのでそのまま残します。複数のパターンは空白なしのカンマでつなぎます（カンマの後の空白は次のパターンの一部になり、一致しなくなります）。`.claude/rules` が原本で、`--update` 時に再生成し（既存プロジェクトは `--update --harness agy` で初回生成）、原本がなくなった生成物は削除します。生成マークのない同名ファイル（ユーザー所有）には触れません。

**サブエージェントアダプタ（#64）。** `.claude/agents/*.md` を Codex（`--harness codex|all`）用の `.codex/agents/<名前>.toml` と agy（`--harness agy|all`）用の `.agents/agents/<名前>.md` として生成します。Codex は `name`・`description`・`developer_instructions`（本文を TOML リテラル文字列 `'''` でそのまま格納）で、本文に `'''` があれば警告してスキップします。agy は `name` と `description` だけを残します — frontmatter に Claude の `tools`・`model`・`memory` があると agy 1.2.16 はそのエージェントを黙って除外するためです（実測）。ツールとモデルは各ハーネスの既定値を継承し、本文の Claude 専用の指示はそのまま残ります。`.claude/agents` が原本なので codex/agy モードでも削除しません。Codex の `.codex/` 層は信頼済みプロジェクトでのみ読み込まれるため、生成しただけでは有効になりません。更新規則はルールアダプタと同じです（`--update` で再生成、原本がなくなった生成物は削除、マークのないユーザーファイルは保持、既存プロジェクトは `--update --harness codex|agy|all` で初回生成）。

**フックアダプタ（#65）。** フックは Claude 形式（`.claude/settings.json` の `hooks` + `.claude/hooks/*`）で書き、`.claude/hooks/hook-adapter.py` が Codex（`--harness codex|all`）用の `.codex/hooks.json` と agy（`--harness agy|all`）用の `.agents/hooks.json` を生成します。実行時も同じアダプタがハーネスの入力を Claude 形式に変換して元のスクリプトを呼び出し、応答をハーネス形式に戻します（2026-10-04 実測）。

- Codex の入力は Claude とほぼ同じです。シェルは `Bash`、ファイル編集は `apply_patch`（パッチテキストからファイルごとに分けて `Edit` として渡す）。Stop の `{"decision":"block"}` をそのまま受け取り、もう 1 ターン回ります。プロジェクトの信頼とフック定義の信頼（`/hooks` での確認）が必要です。
- agy の入力は camelCase（`conversationId`・`toolCall`）です。`run_command` は `Bash`、`write_to_file` などは `Write`/`Edit` に変換し、Stop の `block` は agy の `continue` に変換します。コマンド出力が渡されないため、テスト結果通知は成否を判定できません。**信頼確認なしで実行されます**（clone するだけでリポジトリの `.claude/hooks/*` が動きます — `security-audit` が検査します）。
- 移さないもの: PreToolUse のコミットゲート（`.git/hooks` が担当）、prompt タイプのフック（PreCompact）。
- アダプタには `python3` が必要です（ない場合は生成をスキップ）。`.claude/settings.json` はフックの原本なので codex/agy モードでも残します。
- Stop フック（メモリリマインド）は headless（`-p`・`exec`）でももう 1 ターン回ります。自動化で不要なら `settings.json` から外して `--update` します。更新規則は他のアダプタと同じです。

スキャフォールドは両ハーネスにサブエージェント（#64）とフック（#65）を、agy にパス条件付きルール（#63）を生成し、それぞれ e2e で実測しました。そのため **agy は full**（フックは Claude Code と同じく partial）です。**Codex は baseline のまま**です — ファイルパス条件付きの指示がないため、`.claude/rules` の `paths:` ルールを届ける手段がありません（サブディレクトリの `AGENTS.md` は cwd 基準でのみ読み込まれる）。Claude Code と同じく、フックは早期フィードバックであって強制線ではありません。agy はリポジトリの `.agents/hooks.json` を信頼確認なしで実行するため、外部リポジトリで agy を動かす前にそのファイルを確認してください（`security-audit` エージェントが検査します）。

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

ブートストラップ済みプロジェクトに最新のベースファイル(`.claude/`、`AGENTS.md`)を適用します。
以前のバージョンが生成した `.gemini/settings.json` には触れません(残っていても無害)。
実ディレクトリの `.claude/skills` は、`.agents/skills` が存在しないか内容が同じ場合にのみ原本 `.agents/skills` へ移してリンクにします(#61)。両方が存在し内容が異なる場合は移動せず、手動マージを案内します。移行後はベースの skills も `.agents/skills` 側で更新されます。

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
