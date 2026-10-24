import { expect, test } from "vitest";
import { fitTimes, fmtTime, targetOf } from "./timing.ts";

test("머리말의 목표 길이를 읽는다", () => {
  expect(targetOf("# 대본\n\n- 목표 길이: 60초\n")).toBe(60);
  expect(targetOf("목표 길이 ： 90.5 초")).toBe(90.5);
  expect(targetOf("# 대본")).toBeNull();
  expect(targetOf("목표 길이: 0초")).toBeNull();
});

test("시각 표기", () => {
  expect(fmtTime(1)).toBe("0:01.0");
  expect(fmtTime(72.46)).toBe("1:12.5");
  expect(fmtTime(59.96)).toBe("1:00.0");
});

test("마지막 줄이 목표 길이에서 끝나게 여유를 똑같이 나눈다", () => {
  const { times, spare, gap } = fitTimes(1, [10, 20, 9], 60);
  expect(spare).toBe(20);
  expect(gap).toBeCloseTo(20 / 3);
  expect(times).toEqual([1, 17.7, 44.3]);
  expect(times[2] + 9 + gap).toBeCloseTo(60, 1); // 시각은 0.1초 단위로 반올림한다
});

test("읽는 말이 목표보다 길면 spare 가 음수다", () => {
  expect(fitTimes(1, [40, 30], 60).spare).toBe(-11);
});
