import { expect, test } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse, serialize, SAME } from "./script-md.ts";

// 기본은 스킬 픽스처, EDITOR_CONTENT 를 주면 그 레포의 실제 대본 전부를 왕복 검사한다
const dir = process.env.EDITOR_CONTENT ?? join(dirname(fileURLToPath(import.meta.url)), "../../fixtures");
const files = readdirSync(dir).filter((f) => f.endsWith(".md") && f !== "README.md");

test("대본 파일이 있다", () => {
  expect(files.length).toBeGreaterThan(0);
});

for (const f of files) {
  test(`${f}: parse → serialize 가 원문과 같다`, () => {
    const text = readFileSync(join(dir, f), "utf8");
    expect(serialize(parse(text))).toBe(text);
  });
}

test("수정한 칸이 다시 읽힌다", () => {
  const text = readFileSync(join(dir, files[0]), "utf8");
  const d = parse(text);
  d.rows[0].say = "첫 줄 | 파이프 포함";
  d.rows[0].same = false;
  d.rows[0].speak = "읽는 말";
  d.rows[1].same = true;
  const back = parse(serialize(d));
  expect(back.rows[0].say).toBe("첫 줄 | 파이프 포함");
  expect(back.rows[0].speak).toBe("읽는 말");
  expect(back.rows[1].same).toBe(true);
  expect(serialize(d)).toContain(SAME);
  expect(back.rows.length).toBe(d.rows.length);
});

test("AI 프롬프트: 처음 쓰면 칸을 붙이고, 다시 읽힌다", () => {
  const text = "# 대본\n\n| # | 시각 | 장면 | 화면 자막 | 자막·대본 | 읽는 말 |\n|---|---|---|---|---|---|\n| 1 | 0:01.0 | 인트로 | 제목 | 안녕하세요. | (자막과 같음) |\n| 2 | 0:05.0 | 끝 | 끝 | 끝입니다. | (자막과 같음) |\n";
  const d = parse(text);
  expect(d.hasPrompt).toBe(false);
  expect(serialize(d)).toBe(text);
  d.rows[0].prompt = "버튼으로 줌인 | 클릭 효과\n파란 박스";
  const out = serialize(d);
  expect(out).toContain("| 읽는 말 | AI 프롬프트 |");
  expect(out).toContain("|---|---|---|---|---|---|---|");
  const back = parse(out);
  expect(back.hasPrompt).toBe(true);
  expect(back.hasScreen).toBe(true);
  expect(back.rows[0].prompt).toBe("버튼으로 줌인 | 클릭 효과\n파란 박스");
  expect(back.rows[1].prompt).toBe("");
  expect(serialize(back)).toBe(out);
});

test("AI 프롬프트: 5칸 표에도 붙는다", () => {
  const text = "# 대본\n\n| # | 시각 | 장면 | 자막·대본 | 읽는 말 |\n|---|---|---|---|---|\n| 1 | 0:01.0 | 인트로 | 안녕하세요. | (자막과 같음) |\n";
  const d = parse(text);
  d.rows[0].prompt = "인트로 카드";
  const back = parse(serialize(d));
  expect(back.hasScreen).toBe(false);
  expect(back.rows[0].prompt).toBe("인트로 카드");
});

test("표가 없으면 오류", () => {
  expect(() => parse("# 제목\n\n본문만 있다\n")).toThrow();
});
