use super::*;

fn specs() -> Vec<rules::RuleSpec> {
    rules::load_rules(&default_rules()).unwrap()
}

#[test]
fn python_baseline_findings_and_prose_match() {
    let cases: Value =
        serde_json::from_str(include_str!("../../tests/fixtures/python-baseline.json")).unwrap();
    let engine = Engine::new(specs()).unwrap();
    for case in cases.as_array().unwrap() {
        let text = case["text"].as_str().unwrap();
        let chat = case["chat"].as_bool().unwrap();
        let found = engine.check(text, chat, 60).unwrap();
        assert_eq!(json!(found), case["findings"], "text={text:?}, chat={chat}");
        assert_eq!(
            json!(prose::prose_lines(text)),
            case["prose"],
            "text={text:?}"
        );
    }
}

#[test]
fn lookaround_rules_compile_and_hangul_length_counts_characters() {
    let engine = Engine::new(specs()).unwrap();
    assert!(
        engine
            .check("설정 파일도 포함.", false, 60)
            .unwrap()
            .is_empty()
    );
    assert!(engine.check("일단락됐다.", false, 60).unwrap().is_empty());
    let findings = engine.check(&"가".repeat(61), false, 60).unwrap();
    assert_eq!(findings[0].matched, "61자");
}

#[test]
fn bad_patterns_and_rows_are_errors() {
    let mut rules = specs();
    rules[0].pattern = "(?".into();
    assert!(Engine::new(rules).is_err());
    assert_eq!(rules::split_row(r"| a | b | `x\|y` |"), ["a", "b", "`x|y`"]);
}

#[test]
fn invalid_arguments_are_errors() {
    for args in [
        vec![],
        vec!["--unknown"],
        vec!["--rules"],
        vec!["--max-len", "-1", "-"],
        vec!["--max-len", "0", "-"],
    ] {
        assert!(parse_args(args.into_iter().map(String::from).collect()).is_err());
    }
}

#[test]
fn sentence_boundaries_match_python_whitespace_split() {
    assert_eq!(
        prose::sentences("첫 문장.  다음!\t셋째?\n"),
        ["첫 문장.", "다음!", "셋째?", ""]
    );
}
