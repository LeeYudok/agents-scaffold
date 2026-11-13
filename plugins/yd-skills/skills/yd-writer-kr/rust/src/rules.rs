use fancy_regex::Regex;
use serde::{Deserialize, Serialize};
use std::{fs, path::Path};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RuleSpec {
    pub section: String,
    pub banned: String,
    pub replacement: String,
    pub pattern: String,
}

pub struct Rule {
    pub spec: RuleSpec,
    pub pattern: Regex,
}

pub fn split_row(row: &str) -> Vec<String> {
    let row = row.trim().trim_start_matches('|').trim_end_matches('|');
    let mut cells = Vec::new();
    let mut cell = String::new();
    let mut chars = row.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '\\' && chars.peek() == Some(&'|') {
            cell.push('|');
            chars.next();
        } else if ch == '|' {
            cells.push(cell.trim().to_owned());
            cell.clear();
        } else {
            cell.push(ch);
        }
    }
    cells.push(cell.trim().to_owned());
    cells
}

pub fn load_rules(path: &Path) -> Result<Vec<RuleSpec>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut specs = Vec::new();
    let mut section = String::new();
    for (index, line) in text.lines().enumerate() {
        if let Some(title) = line.strip_prefix("## ") {
            section = title.trim().to_owned();
        }
        if !line.starts_with('|')
            || line
                .chars()
                .all(|c| c == '|' || c == '-' || c.is_whitespace())
        {
            continue;
        }
        let cells = split_row(line);
        if cells.first().is_some_and(|c| c == "금지") {
            continue;
        }
        if cells.len() != 3 {
            return Err(format!(
                "{}:{}: 금지 | 대체 | 검사 세 칸이어야 한다",
                path.display(),
                index + 1
            ));
        }
        if cells[2].is_empty() || cells[2] == "-" {
            continue;
        }
        specs.push(RuleSpec {
            section: section.clone(),
            banned: cells[0].clone(),
            replacement: cells[1].clone(),
            pattern: cells[2].trim_matches('`').to_owned(),
        });
    }
    if specs.is_empty() {
        return Err(format!("{}: 검사 규칙이 없다", path.display()));
    }
    Ok(specs)
}

pub fn compile(specs: Vec<RuleSpec>) -> Result<Vec<Rule>, String> {
    specs
        .into_iter()
        .map(|spec| {
            let pattern = Regex::new(&spec.pattern)
                .map_err(|e| format!("{}: 잘못된 정규식: {e}", spec.banned))?;
            Ok(Rule { spec, pattern })
        })
        .collect()
}
