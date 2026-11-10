# agents-scaffold — 全オプション

`bin/agents-scaffold.sh` の全オプション。概要は [README](../README.ja.md) を参照。

## スタックプリセット

| プリセット | ルールファイル | pre-commit ゲート |
|--------|-----------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `gradle testClasses` / `mvn test-compile`(全テストは `SPRINGBOOT_GATE_TESTS=1`) |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant compile (自動検出) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check`、`mypy` はプロジェクトに設定がある場合のみ |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `php-laravel` | php-laravel.md (paths: app/**/*.php, routes/**/*.php, composer.json) | `composer validate` + `pint --test` + `phpunit` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

`--list-stacks` はこれらの名前を 1 行に 1 つずつ表示します。一覧にない名前はエラー(exit 1)になり、利用できるスタックを表示して、何もインストールしません。以前は警告だけでした。

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

**skills の原本は 1 か所です（#61）。** ハーネスに関係なく skills は `.agents/skills/`（Codex・agy のネイティブパス）に 1 回だけ置き、Claude Code はシンボリックリンク `.claude/skills -> ../.agents/skills` 経由で同じファイルを読みます（claude 2.1.318 で実測 — リンクなしで `.agents/skills` だけを置くと Claude Code は skills を見つけられません）。2 つのコピーが食い違うことはなくなり、後から別のハーネスを加えても再インストールは不要です。

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

git フックは**ハーネスに関係なく常に配線されます**（#21）。Claude Code の `PreToolUse` フックはそのセッションが Bash ツールでコミットしたときにのみ発火するため、早期フィードバック層であって強制線ではありません — 決定的な強制線はハーネスの外（`.git/hooks` + CI）に置きます。既存の pre-commit フックは上書きせず、そこに追加する 1 行を警告で示します。フックは git が実際に実行する場所に書き込みます。worktree、submodule（`.git` がファイル）、`.husky` のような `core.hooksPath` ディレクトリにも対応し、`--update` は欠けているフックを配線します（#106）。[TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md#an-existing-pre-commit-hook-or-husky)（英語）を参照。

選択したスタックの P0 は **`AGENTS.md` 本文に直接挿入**されます。`.claude/rules/` の参照リンクに依存しないため、`.claude/` を読み込まないハーネスでも到達可能です。選択していないスタックは挿入されません（Codex の指示合計はデフォルト 32KiB 上限 — context flooding を防ぐため）。

### 実測検証（2026-11-04）

| ハーネス | 実測バージョン | ティア | baseline | full 層で確認できたこと / できていないこと |
|---|---|---|---|---|
| Claude Code | 2.1.318 | **full** | 成立 | `.claude/rules/*.md` の `paths:` 条件付きロード、サブエージェント、skills、`settings.json` フック — いずれも[公式ドキュメント](https://code.claude.com/docs/en/memory.md)で確認 |
| Codex | codex-cli 0.166.0 | **baseline** | 成立 | `AGENTS.md`、インラインのスタック P0、`.agents/skills`、`.env` ゲート、`.codex/agents` サブエージェント（信頼済みプロジェクトのみ）、`.codex/hooks.json` フック（プロジェクトとフック定義の信頼が必要）、cwd 基準のサブディレクトリ `AGENTS.md` を実測。ファイルパス条件付きの指示はない |
| Antigravity | agy 1.5.0 | **baseline** | 成立 | headless（`-p`）で `AGENTS.md`、インラインのスタック P0、`.agents/skills`、`.env` ゲート、`.agents/agents` サブエージェント、`.agents/hooks.json` フック（信頼確認なしで実行）を実測。**`.agents/rules` の `trigger: glob` ルールは 1.5.0 では一致するファイルを読んでも読み込まれない**（1.4.2 までは pass、`always_on` は正常、#90）。サブディレクトリの `AGENTS.md` は cwd 基準でのみ読み込まれる |

Codex（codex-cli 0.166.0）と agy（1.5.0）は、各モード成果物の AGENTS.md とインラインのスタック P0 をツール呼び出しなしで自動的に読み込み、`.agents/skills` のリポジトリ skills のみを発見しました。どちらも `.claude/skills` は発見しません。agy 1.2.7 の headless は `AGENTS.md` も `GEMINI.md` も読み込めませんでしたが、1.2.16 で解消されています。モデルがルールを見落としても git フックが staged `.env` を exit 2 でブロックします。

サポート状況の単一の真実の源は [`docs/harness-matrix.json`](harness-matrix.json) です。この表はその manifest と突き合わされ、CI では `scripts/dev/check-harness-matrix.py` が検査します — 判定に根拠がない、またはバージョンが食い違う場合、**ビルドは失敗します**。`full` 等級が 90 日以上再実測されていない場合は週次の `harness-matrix` ワークフローが失敗し、プルリクエストでは期限の 14 日前から警告だけを出します。再実測は `scripts/dev/spike-codex-contract.sh --dynamic` と `scripts/dev/spike-agy-contract.sh --dynamic` で行います。

**agy ルールアダプタ（#63）。** `--harness agy|all` では `.claude/rules/*.md` を `.agents/rules/*.md` として生成します。`paths:` があれば `trigger: glob` + `globs:`、なければ `trigger: always_on` になります。パターンは agy 1.2.16 の実測どおりに変換します — スラッシュを含む相対パターン（`src/**`）は `**/src/**` に、スラッシュのないパターン（`Dockerfile`・`*.py`）はファイル名に一致するのでそのまま残します。複数のパターンは空白なしのカンマでつなぎます（カンマの後の空白は次のパターンの一部になり、一致しなくなります）。`.claude/rules` が原本で、`--update` 時に再生成し（既存プロジェクトは `--update --harness agy` で初回生成）、原本がなくなった生成物は削除します。生成マークのない同名ファイル（ユーザー所有）には触れません。

**サブエージェントアダプタ（#64）。** `.claude/agents/*.md` を Codex（`--harness codex|all`）用の `.codex/agents/<名前>.toml` と agy（`--harness agy|all`）用の `.agents/agents/<名前>.md` として生成します。Codex は `name`・`description`・`developer_instructions`（本文を TOML リテラル文字列 `'''` でそのまま格納）で、本文に `'''` があれば警告してスキップします。agy は `name` と `description` だけを残します — frontmatter に Claude の `tools`・`model`・`memory` があると agy 1.2.16 はそのエージェントを黙って除外するためです（実測）。ツールとモデルは各ハーネスの既定値を継承し、本文の Claude 専用の指示はそのまま残ります。`.claude/agents` が原本なので codex/agy モードでも削除しません。Codex の `.codex/` 層は信頼済みプロジェクトでのみ読み込まれるため、生成しただけでは有効になりません。更新規則はルールアダプタと同じです（`--update` で再生成、原本がなくなった生成物は削除、マークのないユーザーファイルは保持、既存プロジェクトは `--update --harness codex|agy|all` で初回生成）。

**フックアダプタ（#65）。** フックは Claude 形式（`.claude/settings.json` の `hooks` + `.claude/hooks/*`）で書き、`.claude/hooks/hook-adapter.py` が Codex（`--harness codex|all`）用の `.codex/hooks.json` と agy（`--harness agy|all`）用の `.agents/hooks.json` を生成します。実行時も同じアダプタがハーネスの入力を Claude 形式に変換して元のスクリプトを呼び出し、応答をハーネス形式に戻します（2026-10-04 実測）。

- Codex の入力は Claude とほぼ同じです。シェルは `Bash`、ファイル編集は `apply_patch`（パッチテキストからファイルごとに分けて `Edit` として渡す）。Stop の `{"decision":"block"}` をそのまま受け取り、もう 1 ターン回ります。プロジェクトの信頼とフック定義の信頼（`/hooks` での確認）が必要です。
- agy の入力は camelCase（`conversationId`・`toolCall`）です。`run_command` は `Bash`、`write_to_file` などは `Write`/`Edit` に変換し、Stop の `block` は agy の `continue` に変換します。コマンド出力が渡されないため、テスト結果通知は成否を判定できません。**信頼確認なしで実行されます**（clone するだけでリポジトリの `.claude/hooks/*` が動きます — `security-audit` が検査します）。
- 移さないもの: PreToolUse のコミットゲート（`.git/hooks` が担当）、prompt タイプのフック、matcher 付きの非ツールイベント（SessionStart `compact` の圧縮リマインド、#72）。
- アダプタには `python3` が必要です（ない場合は生成をスキップ）。`.claude/settings.json` はフックの原本なので codex/agy モードでも残します。
- Stop フック（メモリリマインド）は headless（`-p`・`exec`）でももう 1 ターン回ります。自動化で不要なら `settings.json` から外して `--update` します。更新規則は他のアダプタと同じです。

スキャフォールドは両ハーネスにサブエージェント（#64）とフック（#65）を、agy にパス条件付きルール（#63）を生成し、それぞれ e2e で実測しました。agy は 1.4.2 まで full でしたが、**1.5.0 で glob ルールが読み込まれなくなったため baseline に下げました**（#90）。生成器はそのままにし、agy の修正版が再実測を通れば full に戻します。**Codex は baseline のまま**です — ファイルパス条件付きの指示がないため、`.claude/rules` の `paths:` ルールを届ける手段がありません（サブディレクトリの `AGENTS.md` は cwd 基準でのみ読み込まれる）。Claude Code と同じく、フックは早期フィードバックであって強制線ではありません。agy はリポジトリの `.agents/hooks.json` を信頼確認なしで実行するため、外部リポジトリで agy を動かす前にそのファイルを確認してください（`security-audit` エージェントが検査します）。

Codex 側の制約がもう 2 点、設計に効いてきます。

- **指示の合計はデフォルト 32KiB 上限**（`project_doc_max_bytes`）。そのため選択したスタックの P0 のみを `AGENTS.md` にインライン化します（`--stack javaweb` で実測 6,869 B — 上限の 21%）。
- **`.codex/` レイヤは信頼済みプロジェクトでのみロードされます。** ファイルを生成しても有効化は保証されません。だからこそ決定的な強制線は `.git/hooks` + CI に置きます。

## スキルバンドル (`--with-yd-skills`, `--no-yd-skills`, `--with-personal-skills`)

| インストール | スキル | サブエージェント |
|---|---|---|
| `--lang ko`(デフォルト) | 24 — ワークフロー 10 + `yd-*` 14 | 19 — 7 + `yd-*` 12 |
| `--lang en` | 10 — ワークフロースキル | 7 |
| `--with-personal-skills` を追加 | +9 | +4 |

ワークフロースキル 10 個は `review`・`status`・`search-first`・`security-precheck`・`docs-sync`・`handoff`・
`memory-factcheck`・`skill-evolve`・`grill-me` と、テンプレートの `example-skill` です。`yd-*` 14 個は
[LeeYudok/doksam-skills](https://github.com/LeeYudok/doksam-skills) から移した 13 個(DB・Go・React・TypeScript・ビルド・
画面設計・韓国語ライティングなど)と、依存関係の CVE 点検 `yd-cve-check`(#79)です。付属するエージェント 12 個
(`.claude/agents/yd-*.md`)も一緒にインストールされます(#78)。

| オプション | 効果 |
|---|---|
| `--with-yd-skills` | `yd-*` 14 個とそのエージェントをインストールする。`--lang ko` のデフォルト |
| `--no-yd-skills` | 入れない。`--lang en` のデフォルト。`yd-*` スキルは韓国語で書かれており、英語オーバーレイがないため(#105) |
| `--with-personal-skills` | オプトインバンドル `presets/skills/personal/` もスタックプリセットの後にマージする |

オプトインバンドルはスキル 9 個(`yd-agents-mem`・`yd-claude-auth-sync`・`yd-git-sync`・`yd-git-ship`・`yd-doksam-ui`・
`yd-finguard`・`yd-sdlc-orchestrator`・`yd-script-editor`・`yd-session-recording`)とエージェント 4 個です。
特定の GitLab・ホスト・ui.doksam.com・FinGuard を前提とするため、他の環境向けではありません。

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --stack go --with-yd-skills
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --stack go --with-personal-skills
```

- 選択は `.claude/.scaffold.json`(`yd_skills`、`personal_skills`)に記録され、`--update` は同じセットを維持します。
  このファイルがないインストールでは、`yd-db-expert` があれば `yd-*` セットを、オプトインのスキルが 1 つでもあれば
  オプトインバンドルをインストール済みとみなします。
- デフォルトのインストールを `--update` してもオプトインバンドルは追加されません。`--update --with-yd-skills` は
  既存のインストールに `yd-*` セットを追加します。`--update --no-yd-skills` は記録を変えるだけで、
  インストール済みのスキルは削除しません。
- スキャフォールドなしでスキルだけを入れる方法(プラグイン、`npx skills`、`install-skills.sh`)は
  [SKILLS.en.md](SKILLS.en.md)(英語)にあります。

## 言語 (`--lang`)

ベースツリー(エージェント、ルール、スキル、コマンド、`AGENTS.md`、フック/settings の
メッセージ)は**デフォルトで韓国語**です(#36 での反転 — 韓国語が単一の真実源で、
英語は翻訳オーバーレイ)。`--lang en` は英訳を最後に重ねます — ベースコピー、
forge プリセット、スタックプリセットの後に適用されるため、同じファイルを
`presets/lang/en/base` + `presets/lang/en/forge/<forge>` + `presets/lang/en/stacks/<stack>`
の内容で上書きします。

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`--lang en` では、韓国語のみの `yd-*` スキルも入りません。入れるには `--with-yd-skills` を付けます
([スキルバンドル](#スキルバンドル---with-yd-skills---no-yd-skills---with-personal-skills)を参照)。

`.claude/hooks/pre-commit.sh` は `--lang` によるオーバーレイの対象外です
(スタックパーシャルが挿入されるファイルであり、両言語で 1 つを共有します。コードは
言語の影響を受けません)。言語は `.claude/.scaffold.json` に記録され、`--update` は
その言語でインストールした結果と比較します。英語インストールに韓国語のファイルが
提案されることはなくなりました。

## Usage 1 — script

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge のデフォルトは github。GitLab リポジトリには --forge gitlab を使う
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

`--forge`/`--stack`/`--lang` を省略すると対話モードで実行され、スクリプトが
プロンプトを表示します(forge のデフォルトは github、言語のデフォルトは ko)。存在しない対象ディレクトリは作成されます。

インストールの最後にサマリー(バージョン、ルールファイル・スキル・サブエージェントの数、ゲート)と次の手順が表示されます。
`AGENTS.md` の空のセクションを埋め、ゲートがステージされた `.env` を止めることを確認し、結果をコミットする、という手順です。

### オプション

| オプション | 説明 |
|---|---|
| `<target-dir>` | 対象ディレクトリ。デフォルト `.`。存在しなければ作成する(`--update`・`--uninstall`・`--dry-run` では作成しない) |
| `--forge <forge>` | `github`(デフォルト)または `gitlab` |
| `--lang <lang>` | `ko`(デフォルト)または `en` |
| `--stack <list>` | カンマ区切りのスタックプリセット。省略時は対話的にプロンプト。未知の名前はエラー |
| `--name <name>` | `{{PROJECT_NAME}}` の置換値。デフォルトは対象ディレクトリ名 |
| `--harness <harness>` | `claude`(デフォルト)、`codex`、`agy`、`all` — [ハーネス](#ハーネス---harness)を参照 |
| `--with-yd-skills` / `--no-yd-skills` | 韓国語の `yd-*` スキル 14 個を入れる/入れない。デフォルトは `ko` で入れ、`en` で入れない |
| `--with-personal-skills` | メンテナー環境専用の `yd-*` スキル 9 個とエージェント 4 個もインストール |
| `--yes` | 対話プロンプトをスキップ(非対話モード) |
| `--dry-run` | 何も変更しない。インストール、`--update`、`--uninstall` が行う内容を表示する(後述) |
| `--update` | ブートストラップ済みプロジェクトを更新(後述) |
| `--uninstall` | スキャフォールドがインストールし、あなたが変更していないファイルを削除(後述) |
| `--list-stacks` | 利用できるスタックプリセットを 1 行に 1 つずつ表示 |
| `--version` | スキャフォールドのバージョンを表示(`agents-scaffold 1.0.0`) |
| `-h`、`--help` | 使い方を表示 |

値が必要なオプションに値がないと `Error: --stack needs a value` で、未知のオプションは `Unknown option` で止まります。

### 選択の記録 — `.claude/.scaffold.json`

インストールと `--update` は、使った選択を `.claude/.scaffold.json` に書き込みます(#104)。

```json
{
  "scaffold_version": "1.0.0",
  "name": "my-app",
  "forge": "github",
  "stacks": "nextjs,bun",
  "lang": "en",
  "harness": "claude",
  "yd_skills": "0",
  "personal_skills": "0"
}
```

`--update`・`--uninstall`・`--dry-run` はこれを読み、インストールした内容をそのまま再構築します。`.claude/` の他の
ファイルと一緒にコミットしてください。ファイルがない場合(1.0.0 より前のインストール)は、プロジェクトから選択を推測します
(forge は `rules/forge.md`、スタックは `rules/<stack>.md`、言語は `AGENTS.md` の見出し、ハーネスは存在するディレクトリから)。
このとき最初の出力行は `(recorded)` ではなく `(inferred)` になり、`--update` の最後にファイルが書き込まれます。
コマンドラインのオプションは記録より優先されます。

### プレビュー — `--dry-run`

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --lang en --stack python --dry-run
agents-scaffold/bin/agents-scaffold.sh --update /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
```

対象は一切変更されません。インストールのプレビューは、追加されるファイル数、すでに同一のファイル数、内容が異なる
既存ファイルを表示します。`--update --dry-run` は追加されるファイルと `.new` として置かれるファイルを、
`--uninstall --dry-run` は削除されるファイルと残るファイルを一覧します。対象ディレクトリは存在している必要があります。

### 既存プロジェクトへの再インストール

通常のインストールは繰り返し実行しても安全です(#104)。

- すでにあるベースファイルはそのまま残ります。forge プリセット、スタックプリセット、英語オーバーレイ由来のファイルは
  書き直されます。
- `AGENTS.md` は再生成されます。あなたのファイルが生成結果と異なる場合は、先に `AGENTS.md.bak-<timestamp>` として
  保存されます。必要な内容はそこから戻してください。
- すでに `pre-commit.sh` に入っているスタックゲートが二重に挿入されることはありません。

`AGENTS.md` を再生成せずに更新だけしたい場合は `--update` を使います。

### リモートワンコマンドインストール(クローン不要)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

スクリプトはローカルチェックアウトから実行されていないこと(パイプ実行など)を検知すると、
`AGENTS_SCAFFOLD_REPO` の tarball(デフォルト: `github.com/leeyudok/agents-scaffold`、
環境変数で上書き可)を一時ディレクトリにダウンロードし、テンプレートソースとして
使用します。

| 変数 | 意味 |
|---|---|
| `AGENTS_SCAFFOLD_REPO` | tarball をダウンロードするリポジトリ URL。デフォルトは公式の GitHub リポジトリ |
| `AGENTS_SCAFFOLD_REF` | ダウンロードするブランチまたはタグ。デフォルト `main`。タグは 1.0.0 から使える(#106) |
| `AGENTS_SCAFFOLD_SHA256` | 任意。ダウンロードした tarball の期待 SHA-256。一致しなければインストールを中止する |
| `AGENTS_SCAFFOLD_NO_SYMLINK` | `1` で `.claude/skills` をシンボリックリンクではなくコピーにする |

リリースを固定して検証するには次の形式を使います(リリースタグができた後の書き方で、タグはまだ公開されていません。
[SECURITY.md](../SECURITY.md#installing-safely) を参照)。

```bash
export AGENTS_SCAFFOLD_REF=v1.0.0
export AGENTS_SCAFFOLD_SHA256=<sha256 of that ref's source tarball>
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/v1.0.0/bin/agents-scaffold.sh | bash -s -- --lang en --yes
```

### 更新 — `--update`

ブートストラップ済みプロジェクトを更新します。`--update` は記録された選択を読み、その選択で今インストールした場合の結果を
一時ディレクトリに作り、プロジェクトとファイル単位で比較します(#104)。ベースだけでなく結果全体と比較するため、
forge・スタックプリセット、英語オーバーレイ、`.claude/hooks/pre-commit.sh` も比較対象です。

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo --dry-run
```

| プロジェクト内のファイル | `--update` の動作 |
|---|---|
| 新バージョンと同一 | スキップ |
| 存在しない | 追加 |
| 異なる | そのまま残し、新バージョンを `<file>.new` として書き出す |
| `.claude/memory/MEMORY.md` | あなたのファイル。ない場合だけ追加し、`.new` は作らない |
| 生成アダプター(`.codex/`、`.agents/rules`、`.agents/agents`、`.agents/hooks.json`) | プロジェクトの `.claude/` から再生成 |

- 最後に追加 / 更新保留(`.new`)/ 変更なしのサマリーが出力されます。`.new` は `diff` で確認し、手動で適用してください
  ([TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md#new-files-after---update)、英語)。
- `AGENTS.md` も他のファイルと同じく比較されるので、内容を埋めた後は更新のたびに `AGENTS.md.new` が書き出されます。
- 欠けている git pre-commit フックを配線し、記録された選択を書き戻します。
- コマンドラインのオプションは記録より優先されます。`--update --harness all` は既存プロジェクトに Codex と agy の
  アダプターを追加し、`--update --stack nextjs,go` は別のスタック構成と比較します。
- 以前のバージョンが生成した `.gemini/settings.json` には触れません(残っていても無害)。
- 実ディレクトリの `.claude/skills` は、`.agents/skills` が存在しないか内容が同じ場合にのみ原本 `.agents/skills` へ移して
  リンクにします(#61)。両方が存在し内容が異なる場合は移動せず、手動マージを案内します。移行後はベースの skills も
  `.agents/skills` 側で更新されます。

### 削除 — `--uninstall`

```bash
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --yes
```

記録された選択でインストールした内容を再構築し、それとまだ同一のファイルだけを削除します(#106)。変更したファイルは
残して一覧表示します。`.claude/memory/` と、スキャフォールドが作っていないものは削除しません。git pre-commit フックは、
スキャフォールド自身が書いた 1 行のフックである場合にだけ削除します。`--yes` がなければ確認を求め、確認できる端末が
ない場合は実行しません。

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

`.claude/skills/yd-*/` 配下のファイルは置換しない — `yd-mobile-web-planner` のテンプレートが `{{PROJECT_NAME}}` を成果物用のプレースホルダーとして使うため(#78)。
