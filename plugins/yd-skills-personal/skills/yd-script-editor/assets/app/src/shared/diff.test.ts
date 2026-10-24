import { expect, test } from "vitest";
import { diffChars } from "./diff.ts";

const join = (s: { t: string }[]) => s.map((x) => x.t).join("");

test("같은 문장은 변경 없음", () => {
  const r = diffChars("같은 문장입니다.", "같은 문장입니다.");
  expect(r.a).toEqual([{ t: "같은 문장입니다.", d: false }]);
  expect(r.b).toEqual(r.a);
});

test("바뀐 글자만 표시한다", () => {
  const r = diffChars("요건은 열두 개입니다.", "요건은 열 개입니다.");
  expect(join(r.a)).toBe("요건은 열두 개입니다.");
  expect(join(r.b)).toBe("요건은 열 개입니다.");
  expect(r.a.filter((s) => s.d).map((s) => s.t)).toEqual(["두"]);
  expect(r.b.some((s) => s.d)).toBe(false);
});

test("한쪽이 비면 전부 변경", () => {
  const r = diffChars("", "새 문장");
  expect(r.a).toEqual([]);
  expect(r.b).toEqual([{ t: "새 문장", d: true }]);
});

test("변경 사이의 짧은 일치는 변경으로 합친다", () => {
  const r = diffChars("AI가 개발", "에이아이가 개발");
  expect(join(r.a)).toBe("AI가 개발");
  expect(join(r.b)).toBe("에이아이가 개발");
  expect(r.a[0].d).toBe(true);
});
