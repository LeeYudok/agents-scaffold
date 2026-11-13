use regex::Regex;
use serde::Serialize;
use std::sync::LazyLock;

static LINES: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\r\n|[\n\r\x0B\x0C\x1C-\x1E\x{85}\x{2028}\x{2029}]").unwrap());
static COMMENTS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"<!--.*?-->").unwrap());
static INLINE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`[^`\n]*`").unwrap());
static LINK: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"!?\[([^\]]*)\]\([^)]*\)").unwrap());
static URL: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"https?://\S+").unwrap());
static EMPHASIS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\*\*|__").unwrap());
static HEADING: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\s*#{1,6}\s+").unwrap());
static LIST: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?").unwrap());

#[derive(Debug, Serialize)]
pub struct ProseLine(pub usize, pub String, pub String, pub bool);

pub fn prose_lines(text: &str) -> Vec<ProseLine> {
    let lines: Vec<&str> = LINES.split(text).collect();
    let mut start = 0;
    if lines.first().is_some_and(|s| s.trim() == "---")
        && let Some(end) = lines.iter().skip(1).position(|s| s.trim() == "---")
    {
        start = end + 2;
    }
    let mut out = Vec::new();
    let mut fence: Option<&str> = None;
    let mut in_comment = false;
    for (index, raw) in lines.iter().enumerate().skip(start) {
        let stripped = raw.trim();
        if let Some(marker) = fence {
            if stripped.starts_with(marker) {
                fence = None;
            }
            continue;
        }
        if stripped.starts_with("```") || stripped.starts_with("~~~") {
            fence = Some(&stripped[..3]);
            continue;
        }
        if in_comment {
            if raw.contains("-->") {
                in_comment = false;
            }
            continue;
        }
        if stripped.starts_with("<!--") && !stripped.contains("-->") {
            in_comment = true;
            continue;
        }
        if stripped.is_empty() || stripped.starts_with(['|', '>']) || raw.contains("writer:allow") {
            continue;
        }
        let clean = COMMENTS.replace_all(raw, "");
        let clean = INLINE.replace_all(&clean, "");
        let clean = LINK.replace_all(&clean, "$1");
        let clean = URL.replace_all(&clean, "");
        let clean = EMPHASIS.replace_all(&clean, "");
        let heading = HEADING.is_match(&clean);
        let clean = HEADING.replace(&clean, "");
        let clean = LIST.replace(clean.trim_end(), "");
        if !clean.trim().is_empty() {
            out.push(ProseLine(
                index + 1,
                (*raw).to_owned(),
                clean.trim().to_owned(),
                heading,
            ));
        }
    }
    out
}

pub fn sentences(text: &str) -> Vec<&str> {
    let mut result = Vec::new();
    let mut start = 0;
    let mut previous_end = false;
    let mut splitting = false;
    for (index, ch) in text.char_indices() {
        if ch.is_whitespace() && (previous_end || splitting) {
            if !splitting {
                result.push(&text[start..index]);
            }
            start = index + ch.len_utf8();
            splitting = true;
        } else {
            splitting = false;
        }
        previous_end = matches!(ch, '.' | '?' | '!');
    }
    result.push(&text[start..]);
    result
}
