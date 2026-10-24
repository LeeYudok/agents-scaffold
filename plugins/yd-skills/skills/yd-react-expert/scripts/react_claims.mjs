// SKILL.md 의 React 단언을 실제 react@19 로 재현한다 (이슈 #201).
// verify_react_claims.py 가 임시 디렉터리에 설치한 뒤 `node react_claims.mjs <시나리오>` 로 부른다.
// 시나리오는 관찰값을 JSON 한 줄로 출력할 뿐 판정하지 않는다 — 판정은 파이썬 EXPECT 한 곳이다.
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><body><div id="root"></div></body>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
globalThis.HTMLElement = dom.window.HTMLElement
// React 의 폼 액션은 `new FormData(form)` 을 쓴다. node 기본 FormData 는 jsdom form 을 받지 못한다.
globalThis.FormData = dom.window.FormData
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = await import('react')
const { createRoot } = await import('react-dom/client')
const { renderToString } = await import('react-dom/server')
const { act: reactAct, createElement: h, useState, useEffect, useRef, useDeferredValue, useActionState, use,
  createContext, memo, StrictMode, Suspense } = React

async function mount(el) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  await act(async () => root.render(el))
  return { host, root, render: (e) => act(async () => root.render(e)), unmount: () => act(async () => root.unmount()) }
}
// 프로덕션 빌드의 react 는 act 를 내보내지 않는다. 그때는 타이머로 커밋을 기다린다.
const act = reactAct ?? (async (fn) => { await fn(); await new Promise((r) => setTimeout(r, 20)) })
const tick = () => new Promise((r) => setTimeout(r, 0))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const scenarios = {
  async derived() {
    const rooms = ['alpha', 'beta']
    const n = { effect: 0, calc: 0 }
    const q = 'a'
    const Effect = () => {
      n.effect++
      const [f, setF] = useState([])
      useEffect(() => { setF(rooms.filter((r) => r.includes(q))) }, [])
      return h('p', null, String(f.length))
    }
    const Calc = () => { n.calc++; return h('p', null, String(rooms.filter((r) => r.includes(q)).length)) }
    const ssr = { effect: renderToString(h(Effect)), calc: renderToString(h(Calc)) }
    n.effect = 0; n.calc = 0
    const a = await mount(h(Effect)); const b = await mount(h(Calc))
    return { ssr, renders: n, effectText: a.host.textContent, calcText: b.host.textContent }
  },

  async strictmode() {
    const mk = (log) => () => { useEffect(() => { log.push('mount'); return () => log.push('cleanup') }, []); return null }
    const strict = [], plain = []
    await mount(h(StrictMode, null, h(mk(strict))))
    await mount(h(mk(plain)))
    return { strict, plain, env: process.env.NODE_ENV }
  },

  async race() {
    const pending = {}
    const fetchRoom = (id) => new Promise((res) => { pending[id] = res })
    const mk = (guard) => ({ id }) => {
      const [m, setM] = useState('')
      useEffect(() => {
        let alive = true
        fetchRoom(id).then((v) => { if (!guard || alive) setM(v) })
        return () => { alive = false }
      }, [id])
      return h('p', null, m)
    }
    const out = {}
    for (const guard of [false, true]) {
      const C = mk(guard)
      const t = await mount(h(C, { id: guard ? 'A2' : 'A' }))
      await t.render(h(C, { id: guard ? 'B2' : 'B' }))
      const [a, b] = guard ? ['A2', 'B2'] : ['A', 'B']
      await act(async () => { pending[b](`${b}-msgs`); await tick() })
      await act(async () => { pending[a](`${a}-msgs`); await tick() })
      out[guard ? 'guarded' : 'naive'] = t.host.textContent
    }
    return out
  },

  async indexkey() {
    const out = {}
    for (const mode of ['index', 'id']) {
      const List = ({ ids }) => h('ul', null, ids.map((id, i) => h('li', { key: mode === 'index' ? i : id }, h('input', { 'data-id': id }))))
      const t = await mount(h(List, { ids: ['a', 'b'] }))
      t.host.querySelector('input').value = 'typed-into-a'
      await t.render(h(List, { ids: ['b'] }))
      const input = t.host.querySelector('input')
      out[mode] = { id: input.dataset.id, value: input.value }
    }
    return out
  },

  async keyreset() {
    const Counter = () => { const [n, setN] = useState(0); return h('button', { onClick: () => setN(n + 1) }, String(n)) }
    const t = await mount(h(Counter, { key: 'a' }))
    await act(async () => t.host.querySelector('button').click())
    const afterClick = t.host.textContent
    await t.render(h(Counter, { key: 'a' }))
    const sameKey = t.host.textContent
    await t.render(h(Counter, { key: 'b' }))
    return { afterClick, sameKey, newKey: t.host.textContent }
  },

  async inlinecomponent() {
    const out = {}
    const Hoisted = () => h('input')
    for (const inline of [true, false]) {
      let bump
      const Parent = () => {
        const [n, setN] = useState(0); bump = () => setN(n + 1)
        const Row = () => h('input')
        return h('div', null, h(inline ? Row : Hoisted), h('i', null, String(n)))
      }
      const t = await mount(h(Parent))
      const before = t.host.querySelector('input')
      await act(async () => bump())
      out[inline ? 'inline' : 'hoisted'] = { sameNode: before === t.host.querySelector('input'), attached: before.isConnected }
    }
    return out
  },

  async refprop() {
    const Input = ({ ref }) => h('input', { ref })
    const r = { current: null }
    const t = await mount(h(Input, { ref: r }))
    const refIsInput = r.current instanceof dom.window.HTMLInputElement
    const log = []
    const cb = (node) => { log.push('attach:' + node.tagName); return () => log.push('cleanup') }
    const t2 = await mount(h('div', { ref: cb }))
    await t2.unmount()
    return { refIsInput, log }
  },

  async use() {
    const Ctx = createContext('ctx-default')
    const Cond = ({ on }) => { if (on) { const v = use(Ctx); return h('p', null, v) } return h('p', null, 'off') }
    const p = Promise.resolve('resolved'); p.status = 'fulfilled'; p.value = 'resolved'
    const Prom = () => h('p', null, use(p))
    return {
      ctxOn: renderToString(h(Ctx.Provider, { value: 'provided' }, h(Cond, { on: true }))),
      ctxOff: renderToString(h(Cond, { on: false })),
      promise: renderToString(h(Suspense, { fallback: 'wait' }, h(Prom))),
    }
  },

  async actionstate() {
    const Form = () => {
      const [state, action] = useActionState(async (_prev, fd) => 'saved:' + fd.get('n'), 'init')
      return h('form', { action }, h('input', { name: 'n', defaultValue: 'x' }), h('output', null, state))
    }
    const t = await mount(h(Form))
    const before = t.host.querySelector('output').textContent
    await act(async () => { t.host.querySelector('form').requestSubmit(); await sleep(20) })
    return { before, after: t.host.querySelector('output').textContent }
  },

  async escape() {
    const evil = '<img src=x onerror=alert(1)>'
    return {
      text: renderToString(h('p', null, evil)),
      raw: renderToString(h('p', { dangerouslySetInnerHTML: { __html: evil } })),
    }
  },

  async jsurl() {
    return { html: renderToString(h('a', { href: 'javascript:alert(1)' }, 'x')) }
  },

  async eslint() {
    const { ESLint } = await import('eslint')
    const plugin = (await import('eslint-plugin-react-hooks')).default
    const eslint = new ESLint({
      overrideConfigFile: true,
      overrideConfig: [{
        files: ['**/*.jsx'],
        languageOptions: { ecmaVersion: 2024, sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
        plugins: { 'react-hooks': plugin },
        rules: { 'react-hooks/rules-of-hooks': 'error', 'react-hooks/exhaustive-deps': 'warn' },
      }],
    })
    const lint = async (code) => (await eslint.lintText(code, { filePath: 'x.jsx' }))[0].messages.map((m) => ({ rule: m.ruleId, severity: m.severity, msg: m.message }))
    return {
      missingDep: await lint('import {useEffect} from "react"\nexport function C({q, f}){ useEffect(() => { f(q) }, [q]); return null }'),
      conditionalHook: await lint('import {useState} from "react"\nexport function C({a}){ if (a) { useState(0) } return null }'),
      clean: await lint('import {useEffect} from "react"\nexport function C({q, f}){ useEffect(() => { f(q) }, [q, f]); return null }'),
    }
  },

  async waterfall() {
    const job = () => sleep(120)
    let t = performance.now(); await job(); await job(); const sequential = performance.now() - t
    t = performance.now(); await Promise.all([job(), job()]); const parallel = performance.now() - t
    return { sequential: Math.round(sequential), parallel: Math.round(parallel) }
  },

  async deferred() {
    const log = []
    let set
    const C = () => {
      const [v, setV] = useState('a'); set = setV
      const d = useDeferredValue(v)
      log.push(`${v}/${d}`)
      return h('p', null, d)
    }
    const t = await mount(h(C))
    log.length = 0
    await act(async () => set('b'))
    return { log, text: t.host.textContent }
  },

  async memo() {
    const out = {}
    for (const fresh of [true, false]) {
      let n = 0, bump
      const Child = memo(() => { n++; return null })
      const stable = {}
      const Parent = () => { const [c, setC] = useState(0); bump = () => setC(c + 1); return h(Child, { style: fresh ? {} : stable }) }
      await mount(h(Parent))
      n = 0
      await act(async () => bump())
      out[fresh ? 'freshObject' : 'stableObject'] = n
    }
    return out
  },
}

const name = process.argv[2]
if (!scenarios[name]) { console.error('unknown scenario ' + name); process.exit(2) }
console.log(JSON.stringify(await scenarios[name]()))
process.exit(0)
