import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test } from "vitest";
import { createVideoStore } from "./videos.ts";

async function fixture() {
  const dir = await mkdtemp(join(tmpdir(), "videos-"));
  await writeFile(join(dir, "demo-v10-claude.mp4"), "a");
  await writeFile(join(dir, "demo-v11-claude.mp4"), "bb");
  await writeFile(join(dir, "demo-v11-claude.wav"), "x"); // mp4 만
  await writeFile(join(dir, "sample.mp4"), "x"); // 접두어가 다르면 뺀다
  await mkdir(join(dir, "v11"));
  await writeFile(join(dir, "v11", "v11-check.png"), "png");
  await mkdir(join(dir, "v10-claude"));
  await writeFile(join(dir, "v10-claude", "v10-check.png"), "png");
  await writeFile(join(dir, "videos.json"), JSON.stringify({ "v11-claude": "피드백 반영", "v10-claude": 3 }));
  return dir;
}

test("<접두><key>.mp4 만 목록에 넣고 설명·점검 이미지를 붙인다", async () => {
  const store = createVideoStore(await fixture(), "demo-");
  const list = await store.list();
  expect(list.map((v) => v.key).sort()).toEqual(["v10-claude", "v11-claude"]);
  const v11 = list.find((v) => v.key === "v11-claude")!;
  expect(v11).toMatchObject({ size: 2, desc: "피드백 반영", check: true });
  expect(list.find((v) => v.key === "v10-claude")).toMatchObject({ desc: "", check: true }); // 문자열이 아닌 설명은 버린다
});

test("점검 이미지는 영상별 폴더를 먼저, 없으면 판 폴더를 본다", async () => {
  const dir = await fixture();
  const store = createVideoStore(dir, "demo-");
  expect(await store.checkPath("v10-claude")).toBe(join(dir, "v10-claude", "v10-check.png"));
  expect(await store.checkPath("v11-claude")).toBe(join(dir, "v11", "v11-check.png"));
  expect(await store.checkPath("v9-claude")).toBeNull();
});

test("영상 폴더 밖으로 나가는 key 는 거절한다", async () => {
  const store = createVideoStore(await fixture(), "demo-");
  for (const key of ["../x", "a/b", ".hidden", "", "..", "v11/../../etc"]) {
    expect(store.file(key)).toBeNull();
    expect(await store.checkPath(key)).toBeNull();
  }
});

test("영상 폴더가 없으면 빈 목록", async () => {
  expect(await createVideoStore(join(tmpdir(), "no-such-videos-dir")).list()).toEqual([]);
});
