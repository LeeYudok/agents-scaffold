// 글자 단위 diff — 비교 화면에서 두 대본의 다른 글자를 칠하는 데 쓴다.
// LCS(최장 공통 부분 수열)로 맞추고, 변경 사이에 낀 1~2글자짜리 일치는 변경으로 합쳐 읽기 쉽게 한다.

export type Seg = { t: string; d: boolean };

type Op = { k: "eq" | "del" | "ins" | "both"; t: string };

export function diffChars(a: string, b: string): { a: Seg[]; b: Seg[] } {
  const A = [...a];
  const B = [...b];
  const n = A.length;
  const m = B.length;
  const w = m + 1;
  const dp = new Uint16Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i * w + j] = A[i] === B[j] ? dp[(i + 1) * w + j + 1] + 1 : Math.max(dp[(i + 1) * w + j], dp[i * w + j + 1]);
    }
  }

  const ops: Op[] = [];
  const push = (k: Op["k"], t: string) => {
    const last = ops[ops.length - 1];
    if (last && last.k === k) last.t += t;
    else ops.push({ k, t });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { push("eq", A[i]); i++; j++; }
    else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) push("del", A[i++]);
    else push("ins", B[j++]);
  }
  while (i < n) push("del", A[i++]);
  while (j < m) push("ins", B[j++]);

  ops.forEach((op, k) => {
    if (op.k === "eq" && k > 0 && k < ops.length - 1 && [...op.t].length <= 2) op.k = "both";
  });

  const side = (keep: Op["k"]): Seg[] => {
    const out: Seg[] = [];
    for (const op of ops) {
      if (op.k === "del" || op.k === "ins") { if (op.k !== keep) continue; }
      const d = op.k !== "eq";
      const last = out[out.length - 1];
      if (last && last.d === d) last.t += op.t;
      else out.push({ t: op.t, d });
    }
    return out;
  };
  return { a: side("del"), b: side("ins") };
}
