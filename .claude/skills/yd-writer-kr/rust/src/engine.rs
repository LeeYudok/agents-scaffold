use crate::{
    prose,
    rules::{self, Rule, RuleSpec},
};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::sync::LazyLock;

static EMOJI: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[\x{1F000}-\x{1FAFF}☀-➿\x{FE0F}]").unwrap());
static ISO_TIME: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?[+-]\d{2}:\d{2}")
        .unwrap()
});

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Finding {
    pub line: usize,
    pub level: String,
    pub kind: String,
    #[serde(rename = "match")]
    pub matched: String,
    pub hint: String,
    pub context: String,
}

fn finding(
    line: usize,
    level: &str,
    kind: &str,
    matched: &str,
    hint: String,
    context: &str,
) -> Finding {
    Finding {
        line,
        level: level.into(),
        kind: kind.into(),
        matched: matched.into(),
        hint,
        context: context.chars().take(40).collect(),
    }
}

pub struct Engine {
    rules: Vec<Rule>,
}

impl Engine {
    pub fn new(specs: Vec<RuleSpec>) -> Result<Self, String> {
        Ok(Self {
            rules: rules::compile(specs)?,
        })
    }

    pub fn check(&self, text: &str, chat: bool, max_len: usize) -> Result<Vec<Finding>, String> {
        let mut out = Vec::new();
        for prose::ProseLine(no, raw, clean, heading) in prose::prose_lines(text) {
            for found in EMOJI.find_iter(&raw) {
                out.push(finding(
                    no,
                    "오류",
                    "이모지",
                    found.as_str(),
                    "Phosphor 아이콘이나 글로 바꾼다".into(),
                    &clean,
                ));
            }
            for found in ISO_TIME.find_iter(&raw) {
                out.push(finding(
                    no,
                    "오류",
                    "시각 표기",
                    found.as_str(),
                    "YYYY-MM-DD HH:MM:SS.mmm (KST)".into(),
                    &clean,
                ));
            }
            for sentence in prose::sentences(&clean) {
                let sentence = sentence.trim();
                if sentence.is_empty() {
                    continue;
                }
                for rule in &self.rules {
                    if (chat || heading) && rule.spec.section.starts_with("명사형 종결") {
                        continue;
                    }
                    for found in rule.pattern.find_iter(sentence) {
                        let found = found
                            .map_err(|e| format!("{}: 정규식 실행 실패: {e}", rule.spec.banned))?;
                        out.push(finding(
                            no,
                            "오류",
                            &rule.spec.section,
                            found.as_str(),
                            format!("{} → {}", rule.spec.banned, rule.spec.replacement),
                            sentence,
                        ));
                    }
                }
                let len = sentence.chars().count();
                if !heading && len > max_len {
                    out.push(finding(
                        no,
                        "경고",
                        "긴 문장",
                        &format!("{len}자"),
                        format!("{max_len}자 이하로 나눈다"),
                        sentence,
                    ));
                }
            }
        }
        Ok(out)
    }
}
