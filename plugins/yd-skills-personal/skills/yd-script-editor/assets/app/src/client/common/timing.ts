// 대본 길이 계산: 머리말의 목표 길이, 시각 표기, 목표 길이에 맞춘 시각 배분.

/** 머리말에서 `목표 길이: 60초` 를 찾는다. 없으면 null. */
export function targetOf(before: string): number | null {
  const m = /목표\s*길이\s*[:：]\s*(\d+(?:\.\d+)?)\s*초/.exec(before);
  const v = m ? Number(m[1]) : NaN;
  return v > 0 ? v : null;
}

/** 초 → `m:ss.s` */
export function fmtTime(sec: number): string {
  const t = Math.round(sec * 10) / 10;
  const m = Math.floor(t / 60);
  const s = (t - m * 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

/**
 * 첫 줄 시작 시각을 두고, 줄마다 읽기 시간에 같은 여유를 붙여 마지막 줄이 목표 길이에서 끝나게 시각을 나눈다.
 * spare 는 전체 여유(음수면 읽는 말이 목표보다 길다), gap 은 줄마다 붙인 여유다.
 */
export function fitTimes(start: number, ests: number[], target: number) {
  const spare = target - start - ests.reduce((a, b) => a + b, 0);
  const gap = ests.length ? spare / ests.length : 0;
  const times: number[] = [];
  let t = start;
  for (const est of ests) {
    times.push(Math.round(t * 10) / 10);
    t += est + gap;
  }
  return { times, spare, gap };
}
