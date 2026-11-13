mod engine;
mod prose;
mod rules;

use engine::{Engine, Finding};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    env, fs,
    io::{self, Read},
    path::PathBuf,
};

fn default_limit() -> usize {
    60
}

#[derive(Deserialize)]
struct Request {
    action: String,
    #[serde(default)]
    text: String,
    #[serde(default)]
    chat: bool,
    #[serde(default = "default_limit")]
    max_len: usize,
    rules: Option<Vec<rules::RuleSpec>>,
    rules_path: Option<PathBuf>,
}

struct Options {
    paths: Vec<String>,
    rules: PathBuf,
    chat: bool,
    strict: bool,
    max_len: usize,
    json: bool,
    bridge: bool,
}

fn default_rules() -> PathBuf {
    if let Ok(executable) = env::current_exe() {
        for parent in executable.ancestors().skip(1).take(2) {
            let path = parent.join("references/banned-expressions.md");
            if path.is_file() {
                return path;
            }
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../references/banned-expressions.md")
}

fn parse_args(args: Vec<String>) -> Result<Option<Options>, String> {
    let mut options = Options {
        paths: vec![],
        rules: default_rules(),
        chat: false,
        strict: false,
        max_len: 60,
        json: false,
        bridge: false,
    };
    let mut args = args.into_iter().flat_map(|arg| {
        if arg.starts_with("--max-len=") || arg.starts_with("--rules=") {
            let (key, value) = arg.split_once('=').unwrap();
            vec![key.to_owned(), value.to_owned()]
        } else {
            vec![arg]
        }
    });
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => {
                println!(
                    "yd-writer-kr Rust 글 검사기\nUsage: check-writing [--chat] [--strict] [--max-len N] [--rules FILE] [--json] FILE...\n  -  표준 입력\n종료 코드: 0 오류 없음, 1 글 검사 위반, 2 실행 불가"
                );
                return Ok(None);
            }
            "--version" | "-V" => {
                println!("check-writing {}", env!("CARGO_PKG_VERSION"));
                return Ok(None);
            }
            "--chat" => options.chat = true,
            "--strict" => options.strict = true,
            "--json" => options.json = true,
            "--bridge" => options.bridge = true,
            "--rules" => options.rules = args.next().ok_or("--rules 값이 없다")?.into(),
            "--max-len" => {
                options.max_len = args
                    .next()
                    .ok_or("--max-len 값이 없다")?
                    .parse()
                    .map_err(|_| "--max-len 은 양의 정수여야 한다")?;
                if options.max_len == 0 {
                    return Err("--max-len 은 양의 정수여야 한다".into());
                }
            }
            "--" => {
                options.paths.extend(args);
                break;
            }
            "-" => options.paths.push(arg),
            value if value.starts_with('-') => return Err(format!("알 수 없는 옵션: {value}")),
            _ => options.paths.push(arg),
        }
    }
    if options.paths.is_empty() && !options.bridge {
        return Err("검사할 파일을 지정한다. 표준 입력은 - 를 쓴다".into());
    }
    Ok(Some(options))
}

fn stdin_text() -> Result<String, String> {
    let mut text = String::new();
    io::stdin()
        .read_to_string(&mut text)
        .map_err(|e| format!("표준 입력: {e}"))?;
    Ok(text)
}

fn bridge(options: &Options) -> Result<Value, String> {
    let request: Request =
        serde_json::from_str(&stdin_text()?).map_err(|e| format!("잘못된 JSON 요청: {e}"))?;
    match request.action.as_str() {
        "prose" => Ok(json!(prose::prose_lines(&request.text))),
        "sentences" => Ok(json!(prose::sentences(&request.text))),
        "split_row" => Ok(json!(rules::split_row(&request.text))),
        "rules" | "check" => {
            let specs = match request.rules {
                Some(specs) => specs,
                None => rules::load_rules(request.rules_path.as_ref().unwrap_or(&options.rules))?,
            };
            let engine = Engine::new(specs.clone())?;
            if request.action == "rules" {
                Ok(json!(specs))
            } else {
                Ok(json!(engine.check(
                    &request.text,
                    request.chat,
                    request.max_len
                )?))
            }
        }
        _ => Err(format!("알 수 없는 요청: {}", request.action)),
    }
}

fn report(options: &Options) -> Result<i32, String> {
    if options.bridge {
        println!("{}", bridge(options)?);
        return Ok(0);
    }
    let engine = Engine::new(rules::load_rules(&options.rules)?)?;
    let mut errors = 0;
    let mut warnings = 0;
    let mut reports = Vec::new();
    for path in &options.paths {
        let name = if path == "-" { "<stdin>" } else { path };
        let text = if path == "-" {
            stdin_text()?
        } else {
            fs::read_to_string(path).map_err(|e| format!("{path}: 파일을 읽을 수 없다: {e}"))?
        };
        let findings: Vec<Finding> = engine.check(&text, options.chat, options.max_len)?;
        for finding in &findings {
            if finding.level == "오류" {
                errors += 1;
            } else {
                warnings += 1;
            }
            if !options.json {
                println!(
                    "{name}:{}: {} [{}] '{}' — {}  | {}",
                    finding.line,
                    finding.level,
                    finding.kind,
                    finding.matched,
                    finding.hint,
                    finding.context
                );
            }
        }
        reports.push(json!({"path": name, "findings": findings}));
    }
    if options.json {
        println!(
            "{}",
            json!({"files": reports, "errors": errors, "warnings": warnings})
        );
    } else {
        println!(
            "오류 {errors}건, 경고 {warnings}건{}",
            if options.strict { " (--strict)" } else { "" }
        );
    }
    Ok(i32::from(errors > 0 || (options.strict && warnings > 0)))
}

fn main() {
    let result = parse_args(env::args().skip(1).collect())
        .and_then(|options| options.as_ref().map_or(Ok(0), report));
    match result {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("check-writing: {error}");
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests;
