# agents-scaffold — 内部構造

生成される `.claude/` ツリーと設計パターン。概要は [README](../README.ja.md) を参照。

## 中身

```
.claude/
  agents/
    security-audit.md   12項目の P0/P1 セキュリティ grep スキャン
    db-migration.md      DDL 安全性チェック + ロールバック SQL 生成
    sdlc-developer.md    最小スコープ実装エージェント(SDLC 役割分離)
    sdlc-tester.md        AC/TC テスト作成エージェント
    sdlc-verifier.md      パイプライン実行 + レポートエージェント
    agent-evolve.md       自己改善メタエージェント — 実行フィードバックから agents/*.md を洗練
  commands/              （Claude Code ではレガシー — スラッシュコマンドは skills に統合）
    sonar.md             SonarQube 分析(CE タスクポーリング、sqp_/squ_ トークン処理)
    sdlc-cycle.md         5段階 SDLC 自動化
    knowledge-graph.md    .claude ナレッジグラフ再生成 + リンク切れチェック
  hooks/
    pre-commit.sh         pre-commit ゲートのスケルトン(スタックパーシャルの挿入点)
    post-edit-format.sh   PostToolUse(Edit|Write) → 自動フォーマット
    post-test-notify.sh   PostToolUse(Bash, *test*) → ターミナル通知
    stop-memory-remind.sh Stop フック → セッションごとに1回のメモリリマインダー
    cc-check.py            PostToolUse(Bash, git commit) → CC > 15 なら警告
  memory/
    MEMORY.md              auto-memory インデックス(SSOT)
    README.md               メモリのタイプ/利用ルール
  rules/
    common.md               P0/P1/P2 優先度階層 + 共通ワークフロー(常時ロード)
    security.md              シークレット/認証 P0 + ロックアウト/管理者シーディング規則(paths スコープ)
    testing.md               機能ごとにテスト、mock 優先ユニット、ユーザー視点アサーション
    data.md                  データスクリプト規則 — 一括ステージング禁止、エンコーディング明示
    README.md                paths スコープロード + ルール作成原則
  skills/
    skill-evolve/            自己改善メタスキル(「Learned warnings」パターン)
    status/                   マルチスタック状態チェック
    review/                   code-reviewer + security-audit ラッパー
    memory-factcheck/         メモリのファクトチェック — 主張をコード/DB/イシューと照合し、古いものを修正
    security-precheck/        監査前セキュリティスイープ → イシュー化 → 並列修正
    docs-sync/                ドキュメント現行化 — 主張ごとの事実照合 + 多言語ペアの同時更新
    handoff/                  セッション引き継ぎ — 再開可能な状態を HANDOFF.md / Issue で渡す
  workflows/             （自動ロードされない — 明示的に呼び出す）
    rules-audit.js           保存型 Workflow の例 — scan/verify/repair、マージは人間ゲート
  scripts/               （自動ロードされない — 明示的に呼び出す）
    knowledge_graph.py       .claude エコシステムグラフ + --check リンク切れゲート
  settings.json               フック配線 + デフォルト deny ルール
AGENTS.md                 プロジェクトの頭脳 — ルール SSOT(P0/P1/P2 + ワークフロー)
.gemini/settings.json     Gemini CLI が AGENTS.md を読むよう context.fileName を指定
presets/                  プリセット断片(コピー上書きモデル)
  forge-github/           GitHub forge — gh、PR、`Closes #N` 自動クローズ
  forge-gitlab/           GitLab forge — glab、MR、`Closes #N` 自動クローズ(マージ後に確認)
  nextjs/ bun/ ...        スタック別断片(rules + pre-commit.partial.sh + AGENTS.partial.md)
  lang-en/                英語オーバーレイ(base/forge-*/stacks/*)— 後述の `--lang` を参照
bin/                      agents-scaffold.sh ブートストラップスクリプト
tests/                    ブートストラップスクリプト用 bats リグレッションスイート
```

## 主要パターン

- **P0/P1/P2 優先度階層**: `common.md` + `AGENTS.md` で定義。P0 = セキュリティ/シークレット/データ破壊、例外なし。
- **SDLC 役割分離**: developer/tester/verifier エージェント + `/sdlc-cycle` 自動化コマンド。
- **skill-evolve / agent-evolve**: ミスから「Learned warnings」を追記する自己改善パターン。`skill-evolve` は `.claude/skills/*.md`、`agent-evolve` は `.claude/agents/*.md` が対象。
- **メモリ SSOT**: `.claude/memory/`(システムデフォルトパスは使用しない)。タイプ接頭辞: `project_`/`feedback_`/`reference_`/`user_`。
- **paths スコープのルール**: frontmatter の `paths:` により、マッチするファイルの作業中のみルールを自動ロード。
- **マルチエージェント分離**: 並列サブエージェントが同一ファイルを同時に触る可能性がある場合は `isolation: "worktree"` を使用。
