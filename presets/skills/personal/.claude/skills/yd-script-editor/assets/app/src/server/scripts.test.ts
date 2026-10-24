import { expect, test } from "vitest";
import { assignIds } from "./scripts.ts";

test("새 대본은 다음 번호를 받고 기존 번호는 그대로다", () => {
  const r = assignIds(["a.md", "b.md", "c.md"], { "1": "b.md", "2": "a.md" });
  expect(r.ids).toEqual({ "1": "b.md", "2": "a.md", "3": "c.md" });
  expect(r.byFile).toEqual({ "b.md": 1, "a.md": 2, "c.md": 3 });
  expect(r.changed).toBe(true);
});

test("지운 대본의 번호는 다시 쓰지 않는다", () => {
  const r = assignIds(["a.md", "c.md"], { "1": "a.md", "2": "b.md" });
  expect(r.ids["3"]).toBe("c.md");
  expect(r.byFile["c.md"]).toBe(3);
});

test("바뀐 게 없으면 changed 는 false", () => {
  expect(assignIds(["a.md"], { "1": "a.md" }).changed).toBe(false);
});
