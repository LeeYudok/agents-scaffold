// 자막(화면 표기) → 읽는 말(음성 합성 입력) 변환. OmniVoice 는 한국어 발음 지정이 없어 읽는 대로 적어야 한다
// 영문 약어는 한글 발음으로, 숫자는 한글 수사로 바꾼다. 레포마다 다른 낱말(제품명 등)은 설정 pronounce 표(TSV)로 받는다.

let WORDS: [RegExp, string][] = [];
const escRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** 레포 단어 표(자막 낱말 → 읽는 말). 영문 낱말은 앞뒤가 영문이 아닐 때만 바꾼다(RAG ≠ RAGE). */
export function setWords(pairs: [string, string][]) {
  WORDS = pairs.map(([from, to]) => {
    const src = /^[A-Za-z]/.test(from) ? `(?<![A-Za-z])${escRe(from)}(?![A-Za-z])` : escRe(from);
    return [new RegExp(src, "g"), to];
  });
}

const LETTERS: Record<string, string> = {
  A: "에이", B: "비", C: "씨", D: "디", E: "이", F: "에프", G: "지", H: "에이치", I: "아이", J: "제이", K: "케이", L: "엘", M: "엠",
  N: "엔", O: "오", P: "피", Q: "큐", R: "알", S: "에스", T: "티", U: "유", V: "브이", W: "더블유", X: "엑스", Y: "와이", Z: "지",
};

const DIGIT = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"];

/** 한자어 수: 136110 → 십삼만 육천백십 */
export function sino(n: number): string {
  if (n === 0) return "영";
  const groups: string[] = [];
  const big = ["", "만", "억", "조"];
  for (let g = 0; n > 0; g++, n = Math.floor(n / 10000)) {
    const part = n % 10000;
    if (!part) continue;
    let s = "";
    [1000, 100, 10, 1].forEach((u, k) => {
      const d = Math.floor(part / u) % 10;
      if (!d) return;
      s += (d === 1 && u > 1 ? "" : DIGIT[d]) + ["천", "백", "십", ""][k];
    });
    if (g === 1 && s === "일") s = ""; // 일만 → 만
    groups.unshift(s + big[g]);
  }
  return groups.join(" ");
}

const TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"];
const ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"];

/** 고유어 수(단위 앞): 12 → 열두, 20 → 스무, 202 → 이백두 */
export function native(n: number): string {
  if (n >= 100) return n % 100 ? sino(n - (n % 100)) + native(n % 100) : sino(n);
  if (n === 20) return "스무";
  return TENS[Math.floor(n / 10)] + ONES[n % 10] || sino(n);
}

// 고유어로 세는 단위
const NATIVE_UNITS = ["개", "건", "가지", "명", "곳", "줄", "번"];

export function pronounce(text: string): string {
  let s = text;
  for (const [re, to] of WORDS) s = s.replace(re, to);
  // 숫자 + 단위: 12개 → 열두 개, 100달러 → 백 달러, 1차 → 일차, 1단계 → 일 단계
  s = s.replace(/(?<![\d.:])(\d{1,3}(?:,\d{3})+|\d+)(?![\d.:])(\s*)([가-힣]*)/g, (_m, num: string, _sp: string, unit: string) => {
    const n = Number(num.replace(/,/g, ""));
    const u = NATIVE_UNITS.find((x) => unit.startsWith(x));
    if (u) return `${native(n)} ${unit}`;
    if (!unit) return sino(n);
    if (unit.startsWith("차")) return `${sino(n)}${unit}`;
    return `${sino(n)} ${unit}`;
  });
  // 남은 영문 대문자 약어는 글자별로: SR → 에스알, JPY → 제이피와이
  s = s.replace(/(?<![A-Za-z])[A-Z]{1,6}(?![a-z])/g, (w) => [...w].map((c) => LETTERS[c] ?? c).join(""));
  return s;
}

/**
 * 자막이 old → now 로 바뀌었을 때 읽는 말(speak)의 같은 자리만 고친다. 쉼표·[쉼 …] 같은 직접 편집은 남긴다.
 * 자리를 못 찾으면 null(호출자가 pronounce(now) 로 새로 만든다).
 */
export function patchSpeak(old: string, now: string, speak: string): string | null {
  if (old === now) return speak;
  const a = old.split(/(\s+)/);
  const b = now.split(/(\s+)/);
  let p = 0;
  while (p < a.length && p < b.length && a[p] === b[p]) p++;
  let q = 0;
  while (q < a.length - p && q < b.length - p && a[a.length - 1 - q] === b[b.length - 1 - q]) q++;
  const oldMid = a.slice(p, a.length - q).join("");
  const newMid = b.slice(p, b.length - q).join("");
  const from = pronounce(oldMid).trim();
  const to = pronounce(newMid).trim();
  const ratio = old.length ? a.slice(0, p).join("").length / old.length : 0;

  if (!from) {
    // 끼워 넣기: 앞 단어의 읽는 말 뒤에 붙인다
    const anchor = pronounce(a.slice(0, p).join("").trim().split(/\s+/).pop() ?? "").replace(/[.,!?]+$/, "");
    if (!anchor) return `${to} ${speak}`.trim();
    const at = nearest(speak, anchor, ratio);
    if (at < 0) return null;
    const end = at + anchor.length;
    return `${speak.slice(0, end)} ${to}${speak.slice(end)}`.replace(/ {2,}/g, " ");
  }
  const at = nearest(speak, from, ratio);
  if (at < 0) return null;
  return `${speak.slice(0, at)}${to}${speak.slice(at + from.length)}`.replace(/ {2,}/g, " ").trim();
}

/** text 안에서 needle 이 여러 번 나오면 ratio(자막에서의 상대 위치)에 가장 가까운 곳 */
function nearest(text: string, needle: string, ratio: number): number {
  const hits: number[] = [];
  for (let i = text.indexOf(needle); i >= 0; i = text.indexOf(needle, i + 1)) hits.push(i);
  if (!hits.length) return -1;
  const target = ratio * text.length;
  return hits.reduce((best, h) => (Math.abs(h - target) < Math.abs(best - target) ? h : best));
}
