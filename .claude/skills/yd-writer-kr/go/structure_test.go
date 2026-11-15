package main

import (
	"strings"
	"testing"
)

func kinds(t *testing.T, text string, mode CheckMode) map[string]string {
	t.Helper()
	engine, err := newEngine(nil)
	if err != nil {
		t.Fatal(err)
	}
	if mode.MaxLen == 0 {
		mode.MaxLen = 200
	}
	out := map[string]string{}
	for _, f := range engine.check(text, mode) {
		out[f.Kind] = f.Level
	}
	return out
}

func TestStructureRules(t *testing.T) {
	cases := []struct {
		name, text, kind, level string
		mode                    CheckMode
	}{
		{"같은 종결 3문장", "설정을 바꿀 수 있다. 값을 읽을 수 있다. 결과를 볼 수 있다.", "종결 반복", levelWarning, CheckMode{}},
		{"같은 종결 2문장은 봐준다", "설정을 바꿀 수 있다. 값을 읽을 수 있다. 결과는 로그에 남는다.", "종결 반복", "", CheckMode{}},
		{"서술어가 다르면 봐준다", "설정을 바꾼다. 값을 읽는다. 결과를 본다.", "종결 반복", "", CheckMode{}},
		{"문단이 끊기면 다시 센다", "설정을 바꿀 수 있다. 값을 읽을 수 있다.\n\n결과를 볼 수 있다.", "종결 반복", "", CheckMode{}},
		{"목록의 나란한 종결은 봐준다", "- 설정을 바꿀 수 있다.\n- 값을 읽을 수 있다.\n- 결과를 볼 수 있다.", "종결 반복", "", CheckMode{}},
		{"채팅은 종결 반복을 보지 않는다", "바꿀 수 있어요. 읽을 수 있어요. 볼 수 있어요.", "종결 반복", "", CheckMode{Chat: true}},
		{"산문 모드는 문단 검사를 건너뛴다", "그는 웃고 있었다. 나도 웃고 있었다. 모두 웃고 있었다.", "종결 반복", "", CheckMode{Prose: true}},
		{"문두 접속사 3회", "또한 캐시를 지운다. 그리고 서버를 다시 띄운다. 따라서 로그를 본다.", "문두 접속사", levelWarning, CheckMode{}},
		{"문두 접속사 2회는 봐준다", "또한 캐시를 지운다. 그리고 서버를 다시 띄운다. 로그를 본다.", "문두 접속사", "", CheckMode{}},
		{"접속사로 시작하는 다른 낱말은 봐준다", "그리고서야 끝났다. 따라서는 안 된다. 또한번 돌린다.", "문두 접속사", "", CheckMode{}},
		{"의존명사 3회", "확인할 수 있는 것은 값이 다르다는 점이다.", "의존명사", levelNote, CheckMode{}},
		{"의존명사 2회는 봐준다", "확인할 수 있는 것은 값이다.", "의존명사", "", CheckMode{}},
		{"점수·수정은 의존명사가 아니다", "점수를 수정한 것이다.", "의존명사", "", CheckMode{}},
		{"서술어 콜론 뒤 목록", "다음 순서로 진행합니다:\n\n- 이슈를 등록한다\n- 브랜치를 만든다", "콜론 뒤 목록", levelWarning, CheckMode{}},
		{"명사 뒤 콜론은 봐준다", "진행 순서:\n\n- 이슈를 등록한다", "콜론 뒤 목록", "", CheckMode{}},
		{"콜론 뒤가 목록이 아니면 봐준다", "다음과 같이 진행합니다:\n\n이슈를 등록한다.", "콜론 뒤 목록", "", CheckMode{}},
		{"때마다 콜론은 서술어가 아니다", "알림이 올 때마다:\n- 로그를 본다", "콜론 뒤 목록", "", CheckMode{}},
		{"굵은 머리말 목록 3항목", "- **속도**: 빠르다\n- **안정성**: 높다\n- **비용**: 낮다", "굵은 머리말 목록", levelNote, CheckMode{}},
		{"굵은 머리말 2항목은 봐준다", "- **속도**: 빠르다\n- **안정성**: 높다\n- 비용은 낮다", "굵은 머리말 목록", "", CheckMode{}},
		{"이어지는 줄은 목록을 끊지 않는다", "- **속도**: 빠르다\n  측정값은 표에 있다\n- **안정성**: 높다\n- **비용**: 낮다", "굵은 머리말 목록", levelNote, CheckMode{}},
		{"코드 블록 안은 보지 않는다", "```\n다음을 실행합니다:\n- a\n- **b**: c\n- **d**: e\n- **f**: g\n```", "굵은 머리말 목록", "", CheckMode{}},
		{"writer:allow 줄은 면제한다", "다음 순서로 진행합니다: <!-- writer:allow 인용 -->\n- 이슈를 등록한다", "콜론 뒤 목록", "", CheckMode{}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := kinds(t, c.text, c.mode)[c.kind]; got != c.level {
				t.Fatalf("%s: [%s] = %q, want %q", c.text, c.kind, got, c.level)
			}
		})
	}
}

func TestFindingsStayInLineOrder(t *testing.T) {
	engine, _ := newEngine(nil)
	text := "다음 순서로 진행합니다:\n- 가\n\n확인할 수 있는 것은 값이 다르다는 점이다.\n"
	last := 0
	for _, f := range engine.check(text, CheckMode{MaxLen: 200}) {
		if f.Line < last {
			t.Fatalf("줄 순서가 뒤집혔다: %+v", f)
		}
		last = f.Line
	}
}

func TestNotesDoNotChangeTheExitCode(t *testing.T) {
	var stdout, stderr strings.Builder
	rules := "../references/banned-expressions.md"
	text := "- **속도**: 빠르다\n- **안정성**: 높다\n- **비용**: 낮다\n"
	code := run([]string{"--rules", rules, "--strict", "-"}, strings.NewReader(text), &stdout, &stderr)
	if code != 0 || !strings.Contains(stdout.String(), "참고 1건") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}
