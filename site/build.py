#!/usr/bin/env python3
"""根拠台帳から解説ページ一式を生成する。

  make site  ->  site/dist/*.html

ページに出る件数・部品名・役割はすべて analysis/*.yaml から導出する。
手で書いた数字を混ぜないこと（台帳が変わっても直らないため）。

公開先の URL は site/links.json に置く。参照されたキーが無ければ生成を中断する
（リンク切れのページを黙って出さないため）。
"""
import html
import json
import re
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = ROOT / 'analysis'
COMPONENTS = yaml.safe_load((LEDGER_DIR / 'components.yaml').read_text(encoding='utf-8'))['components']
FACTORS = yaml.safe_load((LEDGER_DIR / 'factors.yaml').read_text(encoding='utf-8'))['factors']
CODE = yaml.safe_load((LEDGER_DIR / 'code.yaml').read_text(encoding='utf-8'))['observations']

SITE = Path(__file__).resolve().parent
DIST = SITE / 'dist'
LINKS_FILE = SITE / 'links.json'

# ページに出す件数は必ずここから引く（固定値を書くと台帳更新で矛盾する）
EVIDENCE_TOTAL = sum(len(e.get('evidence', [])) for e in FACTORS + CODE + COMPONENTS)
if not LINKS_FILE.is_file():
    sys.exit(f'links.json が無い: {LINKS_FILE}')
L = json.loads(LINKS_FILE.read_text(encoding='utf-8'))

# 未設定のキーを '#' に落とすと、リンク切れのページが黙って生成される。
# ここは fail-closed にして、参照された時点で落とす。
_MISSING = set()


def url(key):
    value = L.get(key)
    if not value or not value.startswith('https://'):
        _MISSING.add(key)
        return '#MISSING-' + key
    return value


SERIES = [
    ('sources', '候補ソース', 'stage-sources.html'),
    ('hydrators', 'ハイドレータ', 'stage-hydrators.html'),
    ('filters', 'フィルタ', 'stage-filters.html'),
    ('scoring', '採点', 'stage-scoring.html'),
    ('selection', '選択と出口', 'stage-selection.html'),
]

CSS = r"""<style>
  :root {
    --ground: #eceff3; --surface: #ffffff; --surface-2: #f5f7f9;
    --ink: #151b22; --ink-2: #4a5764; --ink-3: #74818e;
    --line: #cbd4dd; --line-2: #dde4ea;
    --accent: #2b4a6f; --boost: #0d6f68; --suppress: #a3302a; --gate: #9a6a08;
    --shadow: 0 1px 2px rgba(21,27,34,.06), 0 8px 24px rgba(21,27,34,.05);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground: #0e1318; --surface: #161d24; --surface-2: #1b232b;
      --ink: #e4eaf0; --ink-2: #a9b6c2; --ink-3: #7d8b98;
      --line: #2c3841; --line-2: #232d35;
      --accent: #8fb6e2; --boost: #45bdb0; --suppress: #e8776f; --gate: #dda63c;
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
    }
  }
  :root[data-theme="dark"] {
    --ground: #0e1318; --surface: #161d24; --surface-2: #1b232b;
    --ink: #e4eaf0; --ink-2: #a9b6c2; --ink-3: #7d8b98;
    --line: #2c3841; --line-2: #232d35;
    --accent: #8fb6e2; --boost: #45bdb0; --suppress: #e8776f; --gate: #dda63c;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--ground); color: var(--ink);
    font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif;
    font-size: 16px; line-height: 1.75; -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 52px 24px 96px; display: flex; flex-direction: column; gap: 48px; }
  h1, h2 { font-family: ui-serif, "Hiragino Mincho ProN", "Yu Mincho", Georgia, serif; font-weight: 600; text-wrap: balance; margin: 0; letter-spacing: .01em; }
  h1 { font-size: clamp(28px, 5vw, 42px); line-height: 1.25; }
  h2 { font-size: clamp(19px, 3vw, 25px); line-height: 1.35; }
  p { margin: 0; }
  section { display: flex; flex-direction: column; gap: 18px; }
  section > p { max-width: 68ch; }

  .eyebrow { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin: 0 0 8px; }
  .q { font-family: ui-serif, "Hiragino Mincho ProN", "Yu Mincho", Georgia, serif; font-size: 15px; color: var(--ink-2); margin: 0 0 6px; padding-left: 15px; border-left: 2px solid var(--accent); max-width: 60ch; }
  header .lede { font-size: 18px; color: var(--ink-2); margin-top: 16px; max-width: 62ch; }

  /* 連載ナビ */
  .series { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 18px; font-size: 12.5px; }
  .series a, .series span.here, .series span.hub {
    display: inline-block; padding: 3px 11px; border-radius: 13px;
    border: 1px solid var(--line); text-decoration: none; color: var(--ink-3); background: var(--surface);
  }
  .series a:hover { border-color: var(--accent); color: var(--accent); }
  .series span.here { border-color: var(--accent); color: var(--surface); background: var(--accent); }
  .series span.hub, .series a.hub { border-style: dashed; }
  .series .sep { color: var(--ink-3); opacity: .5; }

  figure { margin: 0; background: var(--surface); border: 1px solid var(--line-2); border-radius: 4px; box-shadow: var(--shadow); overflow: hidden; }
  .canvas { overflow-x: auto; padding: 24px 22px 10px; }
  svg { display: block; max-width: 100%; height: auto; min-width: 600px; }
  figcaption { padding: 13px 22px 17px; border-top: 1px solid var(--line-2); background: var(--surface-2); font-size: 13.5px; line-height: 1.65; color: var(--ink-2); }
  figcaption b { color: var(--ink); font-weight: 600; }

  .s-label { font-family: system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif; fill: currentColor; }
  .s-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: currentColor; }
  .s-num { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }
  .stroke { stroke: currentColor; fill: none; }
  .faint { opacity: .28; }
  .muted { opacity: .62; }

  .tablewrap { overflow-x: auto; border: 1px solid var(--line-2); border-radius: 4px; background: var(--surface); box-shadow: var(--shadow); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 10px 13px; border-bottom: 1px solid var(--line-2); vertical-align: top; }
  thead th { font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; background: var(--surface-2); }
  tbody tr:last-child td { border-bottom: none; }
  .ord { width: 2.6em; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; color: var(--ink-3); }
  .nm { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; white-space: nowrap; }
  .note { color: var(--ink-3); font-size: 12.5px; margin-top: 4px; line-height: 1.55; }

  .chip { display: inline-block; font-size: 11.5px; padding: 1px 8px; border-radius: 10px; border: 1px solid currentColor; white-space: nowrap; }
  .chip.author { color: var(--boost); }
  .chip.viewer { color: var(--accent); }
  .chip.system { color: var(--ink-3); }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13.5px; color: var(--ink-2); align-items: center; }

  .split { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 18px; }
  .panel { background: var(--surface); border: 1px solid var(--line-2); border-radius: 4px; box-shadow: var(--shadow); padding: 20px 24px 22px; }
  .panel h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; letter-spacing: .06em; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .panel.can h3 { color: var(--boost); }
  .panel.cannot h3 { color: var(--suppress); }
  .panel ul { font-size: 14.5px; line-height: 1.65; margin: 0; padding-left: 1.1em; }
  .panel li { margin-bottom: 10px; }
  .panel li:last-child { margin-bottom: 0; }
  .panel .to { color: var(--ink-3); font-size: 12.5px; white-space: nowrap; }

  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
  .card {
    display: flex; flex-direction: column; gap: 7px;
    background: var(--surface); border: 1px solid var(--line-2); border-radius: 4px;
    box-shadow: var(--shadow); padding: 19px 21px 21px; text-decoration: none; color: inherit;
    transition: border-color .12s ease, transform .12s ease;
  }
  .card:hover { border-color: var(--accent); transform: translateY(-1px); }
  @media (prefers-reduced-motion: reduce) { .card { transition: none; } .card:hover { transform: none; } }
  .card .kicker { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); }
  .card .name { font-family: ui-serif, "Hiragino Mincho ProN", "Yu Mincho", Georgia, serif; font-size: 19px; font-weight: 600; line-height: 1.3; }
  .card .desc { font-size: 13.5px; color: var(--ink-2); line-height: 1.6; }
  .card .meta { font-size: 12px; color: var(--ink-3); margin-top: 2px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .card:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

  .callout { padding: 14px 18px; border: 1px solid var(--line); border-left: 3px solid var(--gate); border-radius: 3px; background: var(--surface); font-size: 14px; color: var(--ink-2); max-width: 66ch; line-height: 1.65; }
  .callout b { color: var(--ink); font-weight: 600; }

  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .88em; background: var(--surface-2); border: 1px solid var(--line-2); border-radius: 3px; padding: 1px 5px; }
  footer { border-top: 1px solid var(--line); padding-top: 22px; font-size: 13.5px; color: var(--ink-3); max-width: 68ch; line-height: 1.7; }
  a { color: var(--accent); text-underline-offset: 3px; }
  a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
</style>"""


def esc(t):
    return html.escape(' '.join(str(t).split()).replace('**', ''))


def series_nav(current):
    """連載ナビ。current は SERIES のキー、または 'hub' / None。"""
    bits = [f'<a class="hub" href="{url("hub")}">全体像</a>', '<span class="sep">›</span>']
    for i, (key, label, _) in enumerate(SERIES):
        if i:
            bits.append('<span class="sep">›</span>')
        if key == current:
            bits.append(f'<span class="here">{label}</span>')
        else:
            bits.append(f'<a href="{url(key)}">{label}</a>')
    return '<nav class="series">' + ''.join(bits) + '</nav>'


def ipo_svg(uid, inp, proc_title, proc_steps, out, note=''):
    """Input / Process / Output を明示する共通の図。"""
    steps = ''.join(
        f'<text class="s-label" x="450" y="{146 + i * 19}" text-anchor="middle" font-size="11.5" fill="currentColor">{esc(s)}</text>'
        for i, s in enumerate(proc_steps))
    h = 176 + max(len(proc_steps), 2) * 19 + (26 if note else 0)
    mid = 100
    note_el = (f'<text class="s-label muted" x="20" y="{h - 10}" font-size="11.5">{esc(note)}</text>'
               if note else '')
    return f"""<svg viewBox="0 0 900 {h}" role="img" aria-label="この段の入力・処理・出力">
          <defs>
            <marker id="ipo-{uid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <text class="s-mono" x="20" y="24" font-size="11" letter-spacing="2" style="fill: var(--ink-3)">INPUT</text>
          <text class="s-mono" x="450" y="24" font-size="11" letter-spacing="2" text-anchor="middle" style="fill: var(--accent)">PROCESS</text>
          <text class="s-mono" x="880" y="24" font-size="11" letter-spacing="2" text-anchor="end" style="fill: var(--ink-3)">OUTPUT</text>

          <rect x="20" y="40" width="220" height="{h - 76 - (26 if note else 0)}" rx="3" class="stroke faint" stroke-width="1.25" />
          <rect x="300" y="40" width="300" height="{h - 76 - (26 if note else 0)}" rx="3" class="stroke" stroke-width="1.5" style="color: var(--accent)" />
          <rect x="660" y="40" width="220" height="{h - 76 - (26 if note else 0)}" rx="3" class="stroke faint" stroke-width="1.25" />

          <text class="s-label" x="130" y="{mid - 4}" text-anchor="middle" font-size="13" fill="currentColor">{esc(inp[0])}</text>
          <text class="s-label muted" x="130" y="{mid + 16}" text-anchor="middle" font-size="11">{esc(inp[1])}</text>

          <text class="s-label" x="450" y="{mid - 24}" text-anchor="middle" font-size="13.5" style="fill: var(--accent)">{esc(proc_title)}</text>
          {steps}

          <text class="s-label" x="770" y="{mid - 4}" text-anchor="middle" font-size="13" fill="currentColor">{esc(out[0])}</text>
          <text class="s-label muted" x="770" y="{mid + 16}" text-anchor="middle" font-size="11">{esc(out[1])}</text>

          <g class="stroke" stroke-width="1.5" marker-end="url(#ipo-{uid})">
            <line x1="240" y1="{mid}" x2="296" y2="{mid}" />
            <line x1="600" y1="{mid}" x2="656" y2="{mid}" />
          </g>
          {note_el}
        </svg>"""


def comp_table(stage, kind, show_ctl=False, cols=('#', '名前', '役割')):
    items = sorted([c for c in COMPONENTS if c['stage'] == stage and c['kind'] == kind],
                   key=lambda c: c['order'])
    rows = []
    for c in items:
        ctl = (f'<td><span class="chip {c["controlled_by"]}">'
               + {'author': '投稿者', 'viewer': '閲覧者', 'system': '運用'}[c['controlled_by']]
               + '</span></td>') if show_ctl else ''
        note = f'<div class="note">{esc(c["author_note"])}</div>' if c.get('author_note') else ''
        rows.append(f'<tr><td class="ord">{c["order"]}</td><td class="nm">{esc(c["name"])}</td>'
                    f'{ctl}<td>{esc(c["role"])}{note}</td></tr>')
    head = ('<th class="ord">#</th><th>名前</th>'
            + ('<th>誰の都合</th>' if show_ctl else '') + '<th>役割</th>')
    return ('<div class="tablewrap"><table><thead><tr>' + head + '</tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def n(stage, kind):
    return len([c for c in COMPONENTS if c['stage'] == stage and c['kind'] == kind])


def n_ctl(kind, controlled_by, stage='main'):
    return len([c for c in COMPONENTS
                if c['stage'] == stage and c['kind'] == kind and c['controlled_by'] == controlled_by])


AVAIL = ('default_on', 'default_off', 'conditional')


def sources_sorted():
    """図に出す順。有効なものを上に、上限の大きい順。上限なしは最後。"""
    srcs = [c for c in COMPONENTS if c['kind'] == 'source']
    for c in srcs:
        if c.get('availability') not in AVAIL or 'limit_default' not in c:
            sys.exit(f"NG: source {c['name']} に availability / limit_default が無い（図を組み立てられない）")
    rank = {'default_on': 0, 'conditional': 2, 'default_off': 1}
    return sorted(srcs, key=lambda c: (rank[c['availability']], -(c['limit_default'] or 0), c['order']))


def n_disabled_sources():
    return len([c for c in COMPONENTS
                if c['kind'] == 'source' and c.get('availability') == 'default_off'])


def sources_chart_svg():
    """候補ソースの上限バーチャートを台帳から生成する。"""
    rows = sources_sorted()
    top, step, x0, maxw = 34, 34, 216, 480
    limits = [c['limit_default'] for c in rows if c['limit_default']]
    scale = maxw / max(limits) if limits else 1
    labels, bars, values, notes = [], [], [], []
    for i, c in enumerate(rows):
        y = top + i * step
        av, lim = c['availability'], c['limit_default']
        dim = '' if av == 'default_on' else ' class="muted"'
        labels.append(f'<text x="200" y="{y + 12}"{dim}>{esc(c["name"])}</text>')
        if lim:
            w = round(lim * scale)
            if av == 'default_on':
                bars.append(f'<rect x="{x0}" y="{y}" width="{w}" height="16" fill="currentColor" '
                            f'style="color: var(--boost)" />')
            else:
                bars.append(f'<rect x="{x0}" y="{y}" width="{w}" height="16" class="stroke" '
                            f'stroke-width="1.25" stroke-dasharray="5 4" style="color: var(--ink-3)" />')
            values.append(f'<text x="{x0 + w + 10}" y="{y + 13}"{dim}>{lim}</text>')
        else:
            bars.append(f'<rect x="{x0}" y="{y}" width="400" height="16" class="stroke faint" '
                        f'stroke-width="1.25" stroke-dasharray="2 4" />')
            notes.append(f'<text x="{x0 + 410}" y="{y + 13}" class="muted" font-size="10.5">'
                         f'条件付きで動く（上限の定数なし）</text>')
    h = top + len(rows) * step + 44
    return f'''<svg viewBox="0 0 900 {h}" role="img" aria-label="{len(rows)} つの候補ソースの既定上限件数と有効・無効">
          <g class="s-label" font-size="12.5" text-anchor="end" fill="currentColor">
            {chr(10).join(labels)}
          </g>
          {chr(10).join(bars)}
          <g class="s-num" font-size="12" text-anchor="start" fill="currentColor">
            {chr(10).join(values)}
          </g>
          <g class="s-label" fill="currentColor">
            {chr(10).join(notes)}
          </g>
          <text class="s-mono" x="{x0}" y="{h - 14}" font-size="10.5" style="fill: var(--ink-3)">実線 = 既定で有効 ／ 破線 = 既定で無効 ／ 点線 = 条件付きで動く</text>
        </svg>'''


# よく使う件数。散文にも見出しにも、ここから引いた値だけを埋める
N_SRC = n('main', 'source')
N_HYD = n('main', 'hydrator')
N_FIL = n('main', 'filter')
N_SCO = n('main', 'scorer')
N_PS_HYD = n('post_selection', 'hydrator')
N_PS_FIL = n('post_selection', 'filter')
N_SRC_OFF = n_disabled_sources()
N_FIL_AUTHOR = n_ctl('filter', 'author')
N_FIL_VIEWER = n_ctl('filter', 'viewer')
N_FIL_SYSTEM = n_ctl('filter', 'system')


FOOT = """  <footer>
    <p>
      対象は <code>xai-org/x-algorithm</code> の commit <code>a389166f</code>（Apache-2.0）。
      記述はすべて、ピン留めした commit の実ファイルと機械照合済みの根拠台帳から起こしている。
      公開されているのは実装の一部であり、本番の設定値・学習済みモデルは含まれない。
    </p>
  </footer>"""


def page(title, body):
    """公開用のフラグメント。Artifact 側が <!doctype>/<head>/<body> を付ける。"""
    return f'<title>{title}</title>\n\n{CSS}\n\n<div class="wrap">\n{body}\n</div>\n'


def standalone(fragment):
    """ローカルで開く用に、charset 付きの完全な HTML 文書へ包む。

    公開物 (dist/*.html) は骨組みを持たない仕様なので、そのまま file:// で開くと
    charset が未宣言になり日本語が化ける。閲覧用はこちらを使う。
    """
    title = re.search(r'<title>.*?</title>', fragment, re.S).group(0)
    style = re.search(r'<style>.*?</style>', fragment, re.S)
    body = fragment[style.end():]
    return ('<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'{title}\n{style.group(0)}\n</head>\n<body>\n{body}\n</body>\n</html>\n')


def header(title, lede, current):
    return f"""  <header>
    <p class="eyebrow">xai-org/x-algorithm · a389166f</p>
    <h1>{title}</h1>
    <p class="lede">{lede}</p>
    {series_nav(current)}
  </header>"""


# ═══════════════════════════ 画報 1: 候補ソース
SOURCES = header(
    '候補ソース',
    'タイムラインに出る前に、まず<b>候補として拾われる</b>必要がある。'
    f'その入口が {N_SRC} 本あり、それぞれ別の理屈で投稿を連れてくる。',
    'sources') + f"""

  <section>
    <div><p class="eyebrow">概念</p><h2>{N_SRC} 本の網を同時に投げている</h2></div>
    <p>
      候補集めは「1 本の検索」ではない。フォロー中の投稿を取る網、興味の近い投稿を取る網、
      話題から取る網が<b>並行して投げられ、獲れたものが 1 つの籠にまとめられる</b>。
      どの網にも掛からなければ、その投稿は以降の段に一度も現れない。
    </p>
    <p>
      網ごとに獲れる上限が決まっていて、しかも <b>{N_SRC} 本のうち {N_SRC_OFF} 本は既定で畳まれている</b>。
      「候補が無限にあってそこから選ばれる」のではなく、入口の時点ですでに絞られている。
    </p>
  </section>

  <section>
    <div><p class="eyebrow">Input / Process / Output</p><h2>この段の入力と出力</h2></div>
    <figure>
      <div class="canvas">
        {ipo_svg(1,
                 ('利用者の手がかり', '利用者 ID・最近反応した投稿・リクエストの種類'),
                 f'{N_SRC} 本の候補ソースを実行する',
                 ['フォロー中の投稿を取る（Thunder）',
                  '興味の近い投稿を取る（SimClusters・Phoenix）',
                  '話題・キャッシュから取る',
                  '各ソースが上限件数まで取得する'],
                 ('候補投稿の集合', '重複あり・属性はまだ無い'),
                 f'既定で無効なソースが {N_SRC_OFF} 本ある。動く本数はリクエストの種類でも変わる。')}
      </div>
      <figcaption>
        入口には「その投稿がよいか」の判断は無い。<b>誰の何に近いか、いつのものか</b>で拾われる。
        投稿の中身を見た評価が始まるのは、ここから 2 段あと。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図</p><h2>ソースごとの上限と、既定の有効・無効</h2></div>
    <figure>
      <div class="canvas">
        {sources_chart_svg()}
      </div>
      <figcaption>
        <b>上限の合計は入口の実数ではない。</b>各ソースは同じ投稿を返しうるし、条件付きのソースは動かないこともある。
        合計値をコードから導くことはできないので、この先の図でも「入口の総数」は空白のままにしてある。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">定義</p><h2>{N_SRC} 本それぞれ</h2></div>
    {comp_table('main', 'source')}
  </section>

  <section>
    <div><p class="eyebrow">深堀り</p><h2>ここで分かること・分からないこと</h2></div>
    <div class="split">
      <div class="panel can">
        <h3>コードから言える</h3>
        <ul>
          <li>入口は {N_SRC} 本で、うち {N_SRC_OFF} 本は既定で無効</li>
          <li>1 本あたりの上限は 200〜1200 件</li>
          <li>SimClusters と TweetMixer は 48 時間以内の投稿に限る</li>
        </ul>
      </div>
      <div class="panel cannot">
        <h3>コードからは言えない</h3>
        <ul>
          <li>{N_SRC} 本合計で何件集まるか（重複排除は後段なので単純な足し算にならない）</li>
          <li>Phoenix retrieval が何を根拠に投稿を選ぶか（モデルは非公開）</li>
          <li>どのソース経由が最終的に残りやすいか</li>
        </ul>
      </div>
    </div>
    <div class="callout">
      次は <a href="{url('hydrators')}">ハイドレータ</a>。
      ここで集めた候補はまだ ID の束に近く、落とすかどうかを判断する材料が付いていない。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ 画報 2: ハイドレータ
HYDRATORS = header(
    'ハイドレータ',
    '集めた候補は<b>まだ判断できない</b>。誰が書いたか、動画が付いているか、'
    'フォロー関係はどうか。それを外から取ってきて貼るのがこの段。',
    'hydrators') + f"""

  <section>
    <div><p class="eyebrow">概念</p><h2>候補に「身元」を付ける段</h2></div>
    <p>
      ソースから来た候補は、乱暴に言えば投稿 ID の束でしかない。
      これを <b>{N_HYD} 個のハイドレータが順に外部サービスへ問い合わせ、属性を書き込んでいく</b>。
      フォロー関係、著者のアカウント属性、メディアの有無、実測のいいね数——
      次の段で「落とすかどうか」を決めるための材料が、ここで揃う。
    </p>
    <p>
      重要なのは、<b>フィルタは投稿そのものを見ていない</b>ということ。
      見ているのはこの段で貼られた属性であって、属性が付かなければ判断もできない。
    </p>
  </section>

  <section>
    <div><p class="eyebrow">Input / Process / Output</p><h2>この段の入力と出力</h2></div>
    <figure>
      <div class="canvas">
        {ipo_svg(2,
                 ('候補投稿の集合', '投稿 ID 中心。判断材料はまだ無い'),
                 f'{N_HYD} 個のハイドレータを順に適用する',
                 ['フォロー関係を判定して書き込む',
                  '著者の属性・メディア・言語を取得する',
                  '実測のいいね数・返信数を取得する',
                  '外部サービスへの問い合わせは並行して行う'],
                 ('属性の付いた候補', '落とす／点を付ける判断ができる状態'),
                 '問い合わせに失敗した属性は空のまま次段へ進む（処理は止まらない）。')}
      </div>
      <figcaption>
        この段は候補を<b>1 件も減らさない</b>。増やしもしない。ただ情報を厚くするだけ。
        にもかかわらず、次の段の結果はここで決まる。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図</p><h2>どのハイドレータが、どのフィルタの材料を書いているか</h2></div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 900 400" role="img" aria-label="ハイドレータが書き込むフィールドと、それを判定に使うフィルタの対応関係">
          <defs>
            <marker id="hy" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <text class="s-mono" x="20" y="24" font-size="10.5" style="fill: var(--accent)">ハイドレータ（書く）</text>
          <text class="s-mono" x="360" y="24" font-size="10.5" style="fill: var(--ink-3)">書き込む値</text>
          <text class="s-mono" x="620" y="24" font-size="10.5" style="fill: var(--accent)">フィルタ（読む）</text>
          <g class="s-mono" font-size="11" fill="currentColor">
            <text x="20" y="60">1 InNetwork</text>
            <text x="20" y="100">3 CoreData</text>
            <text x="20" y="140">5 MediaInfo</text>
            <text x="20" y="180">6 Subscription</text>
            <text x="20" y="220">7 Gizmoduck</text>
            <text x="20" y="260">8 BlockedBy</text>
            <text x="20" y="300">9 FilteredTopics</text>
            <text x="20" y="340">11 EngagementCounts</text>
          </g>
          <g class="s-mono muted" font-size="10.5" text-anchor="middle" fill="currentColor">
            <text x="440" y="60">in_network</text>
            <text x="440" y="100">author_id</text>
            <text x="440" y="140">min_video_duration_ms</text>
            <text x="440" y="180">subscription_author_id</text>
            <text x="440" y="220">nsfw_author</text>
            <text x="440" y="260">author_blocks_viewer</text>
            <text x="440" y="300">filtered_topic_ids</text>
            <text x="440" y="340">fav_count 他</text>
          </g>
          <g class="s-mono" font-size="11" text-anchor="end" fill="currentColor">
            <text x="880" y="60">5 OONRetweetReply</text>
            <text x="880" y="100">2 CoreDataHydration</text>
            <text x="880" y="140">14 Video</text>
            <text x="880" y="180">8 IneligibleSubscription</text>
            <text x="880" y="220">6 OONNsfwSimclusters</text>
            <text x="880" y="260">13 AuthorSocialgraph</text>
            <text x="880" y="300">15 TopicIds</text>
            <text x="880" y="340">16 NewUserMinEngagement</text>
          </g>
          <g class="stroke faint" stroke-width="1" marker-end="url(#hy)">
            <line x1="150" y1="56" x2="350" y2="56" /><line x1="530" y1="56" x2="740" y2="56" />
            <line x1="150" y1="96" x2="350" y2="96" /><line x1="530" y1="96" x2="740" y2="96" />
            <line x1="150" y1="136" x2="350" y2="136" /><line x1="530" y1="136" x2="740" y2="136" />
            <line x1="150" y1="176" x2="350" y2="176" /><line x1="530" y1="176" x2="740" y2="176" />
            <line x1="150" y1="216" x2="350" y2="216" /><line x1="530" y1="216" x2="740" y2="216" />
            <line x1="150" y1="256" x2="350" y2="256" /><line x1="530" y1="256" x2="740" y2="256" />
            <line x1="150" y1="296" x2="350" y2="296" /><line x1="530" y1="296" x2="740" y2="296" />
            <line x1="150" y1="336" x2="350" y2="336" /><line x1="530" y1="336" x2="740" y2="336" />
          </g>
          <text class="s-label muted" x="20" y="384" font-size="11">数字は各段での配線順。{N_HYD} 個のうち、フィルタの判定に直接使われるものを抜き出した。</text>
        </svg>
      </div>
      <figcaption>
        <b>この対応は、書き込み側と読み取り側の 2 つの根拠から導いている。</b>
        ハイドレータ側の <code>candidate.nsfw_author = ...</code> と、フィルタ側の
        <code>c.nsfw_author == Some(true)</code> が同じフィールドを指していることによる。
        呼び出し関係を直接たどったものではない。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">定義</p><h2>{N_HYD} 個それぞれ</h2></div>
    {comp_table('main', 'hydrator')}
  </section>

  <section>
    <div><p class="eyebrow">深堀り</p><h2>失敗しても処理は止まらない</h2></div>
    <p>
      属性の取得は外部サービスへの問い合わせなので、失敗しうる。
      このパイプラインは<b>失敗した属性を空のまま次に進める</b>設計になっている。
      サービス全体が落ちない代わりに、<b>属性が欠けた候補が静かに次段へ流れる</b>。
    </p>
    <div class="callout">
      属性が空だとどうなるかはフィルタ側の書き方しだい。
      たとえば経過時間を計算できない候補は「落とす」側に倒れ、
      フォロー判定が付かなかった候補は「フォロー内と同じ扱い」で通る。
      <b>安全側の倒し方が場所によって違う</b>のは、次の <a href="{url('filters')}">フィルタ</a> で見える。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ 画報 3: フィルタ
FILTERS = header(
    'フィルタ',
    '点を付ける前に、<b>0 か 1 で落とす</b>関門が {N_FIL} 個。'
    'ここで落ちた候補は、どれだけ良い投稿でも二度と戻ってこない。',
    'filters') + f"""

  <section>
    <div><p class="eyebrow">概念</p><h2>関門は直列。1 つでも引っかかれば終わり</h2></div>
    <p>
      フィルタは点数ではない。<b>通るか落ちるかの二択</b>で、{N_FIL} 個が一列に並んでいる。
      前の段で貼られた属性を見て、条件に当たれば落とす。
      スコアで挽回するという発想が通じないのは、そもそも採点まで到達しないから。
    </p>
    <p>
      並びには意味がある。前半は<b>データの整合と投稿の性質</b>（重複・経過時間・投稿の形式）、
      後半は<b>その閲覧者にとって出してよいか</b>（既読・ミュート・ブロック・購読）。
      つまり同じ投稿でも、<b>誰のタイムラインを組んでいるかで結果が変わる</b>。
    </p>
  </section>

  <section>
    <div><p class="eyebrow">Input / Process / Output</p><h2>この段の入力と出力</h2></div>
    <figure>
      <div class="canvas">
        {ipo_svg(3,
                 ('属性の付いた候補', 'フォロー関係・著者属性・メディア等'),
                 f'{N_FIL} 個のフィルタを順に適用する',
                 ['重複・データ欠落を落とす',
                  '経過時間と投稿の形式で落とす',
                  '閲覧者の既読・ミュート・ブロックで落とす',
                  '効果測定用のホールドアウトで落とす'],
                 ('生き残った候補', 'ここから採点に進む'),
                 '各フィルタは条件付きで無効化されうるので、常に {N_FIL} 個すべてが評価されるとは限らない。')}
      </div>
      <figcaption>
        この段は候補を<b>減らすだけ</b>で、順番も点数も付けない。
        減った結果が何件になるかはコードに書かれていない。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図 1</p><h2>{N_FIL} 個の並びと、誰の都合で効くか</h2></div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 900 250" role="img" aria-label="{N_FIL} 個のフィルタが直列に並ぶ図。投稿者が影響できるのは {N_FIL_AUTHOR} 個だけ">
          <text class="s-label muted" x="20" y="26" font-size="11.5">候補はこの {N_FIL} 個を順に通り、どれか 1 つで落ちればそこで終わる</text>
          <g stroke-width="1.5">
            <rect x="20" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--ink-3)" />
            <rect x="70" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--ink-3)" />
            <rect x="120" y="44" width="44" height="44" rx="3" fill="currentColor" style="color: var(--boost)" />
            <rect x="170" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--ink-3)" />
            <rect x="220" y="44" width="44" height="44" rx="3" fill="currentColor" style="color: var(--boost)" />
            <rect x="270" y="44" width="44" height="44" rx="3" fill="currentColor" style="color: var(--boost)" />
            <rect x="320" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--ink-3)" />
            <rect x="370" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="420" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="470" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="520" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="570" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="620" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="670" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="720" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="770" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--accent)" />
            <rect x="820" y="44" width="44" height="44" rx="3" class="stroke" style="color: var(--ink-3)" />
          </g>
          <g class="s-num" font-size="12" text-anchor="middle">
            <text x="42" y="72" fill="currentColor" class="muted">1</text>
            <text x="92" y="72" fill="currentColor" class="muted">2</text>
            <text x="142" y="72" fill="var(--surface)">3</text>
            <text x="192" y="72" fill="currentColor" class="muted">4</text>
            <text x="242" y="72" fill="var(--surface)">5</text>
            <text x="292" y="72" fill="var(--surface)">6</text>
            <text x="342" y="72" fill="currentColor" class="muted">7</text>
            <text x="392" y="72" style="fill: var(--accent)">8</text>
            <text x="442" y="72" style="fill: var(--accent)">9</text>
            <text x="492" y="72" style="fill: var(--accent)">10</text>
            <text x="542" y="72" style="fill: var(--accent)">11</text>
            <text x="592" y="72" style="fill: var(--accent)">12</text>
            <text x="642" y="72" style="fill: var(--accent)">13</text>
            <text x="692" y="72" style="fill: var(--accent)">14</text>
            <text x="742" y="72" style="fill: var(--accent)">15</text>
            <text x="792" y="72" style="fill: var(--accent)">16</text>
            <text x="842" y="72" fill="currentColor" class="muted">17</text>
          </g>
          <g class="stroke" stroke-width="1" stroke-dasharray="3 3" style="color: var(--boost)">
            <line x1="142" y1="88" x2="142" y2="118" />
            <line x1="242" y1="88" x2="242" y2="140" />
            <line x1="292" y1="88" x2="292" y2="118" />
          </g>
          <g class="s-label" font-size="11.5" text-anchor="middle" style="fill: var(--boost)">
            <text x="142" y="134">48 時間を過ぎたら落ちる</text>
            <text x="292" y="134">著者が NSFW 判定なら落ちる</text>
            <text x="242" y="156">フォロー外の RT・リプライは落ちる</text>
          </g>
          <g class="s-label" font-size="11.5">
            <text x="20" y="196" style="fill: var(--boost)">■ 投稿者が影響できる（{N_FIL_AUTHOR} 個）</text>
            <text x="270" y="196" style="fill: var(--accent)">□ 閲覧者の設定・履歴で決まる（{N_FIL_VIEWER} 個）</text>
            <text x="600" y="196" style="fill: var(--ink-3)">□ 運用・整合のため（{N_FIL_SYSTEM} 個）</text>
          </g>
          <text class="s-label muted" x="20" y="226" font-size="11.5">後半はほぼ閲覧者側の事情。同じ投稿でも、誰のタイムラインかで結果が変わる。</text>
        </svg>
      </div>
      <figcaption>
        <b>投稿者が動かせるのは前半の {N_FIL_AUTHOR} 個だけ。</b>
        残りは投稿の良し悪しとは無関係な理由で落ちる。
        「良い投稿なのに伸びない」の一部は、ここで説明がつく。
      </figcaption>
    </figure>
  </section>

  <section>
    <div>
      <p class="eyebrow">図 2</p>
      <p class="q">フォロー外の人に届く投稿と、届かない投稿は何が違う？</p>
      <h2>形式だけで足切りされる。中身は見られていない</h2>
    </div>
    <p>
      {N_FIL} 個のうち 5 番目のフィルタは、<b>投稿の形式とフォロー関係の掛け算</b>だけで落とす。
      内容は一切見ない。この 1 個の挙動を表にすると次のようになる。
    </p>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 880 268" role="img" aria-label="フォロー関係と投稿形式の組み合わせごとに、候補が通過するか除外されるかを示す表">
          <g class="s-label" font-size="12" text-anchor="middle">
            <text x="270" y="30">単独ポスト</text>
            <text x="440" y="30">リプライ</text>
            <text x="610" y="30">リプライ</text>
            <text x="780" y="30">リポスト</text>
          </g>
          <g class="s-mono muted" font-size="9.5" text-anchor="middle">
            <text x="270" y="45">reply/RT でない</text>
            <text x="440" y="45">祖先あり</text>
            <text x="610" y="45">祖先なし</text>
            <text x="780" y="45">retweeted_id あり</text>
          </g>
          <g class="s-label" font-size="12.5" text-anchor="end">
            <text x="172" y="88">フォロー内</text>
            <text x="172" y="150">フォロー外</text>
            <text x="172" y="212">判定できず</text>
          </g>
          <g class="s-mono muted" font-size="9.5" text-anchor="end">
            <text x="172" y="103">in_network = true</text>
            <text x="172" y="165">in_network = false</text>
            <text x="172" y="227">in_network = None</text>
          </g>
          <g stroke-width="1.25">
            <rect x="190" y="62" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
            <rect x="360" y="62" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
            <rect x="530" y="62" width="160" height="52" rx="3" fill="none" stroke="currentColor" stroke-dasharray="4 3" style="color: var(--suppress)" />
            <rect x="700" y="62" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
          </g>
          <g class="s-label" font-size="13" text-anchor="middle">
            <text x="270" y="94" style="fill: var(--boost)">通過</text>
            <text x="440" y="94" style="fill: var(--boost)">通過</text>
            <text x="610" y="94" style="fill: var(--suppress)">除外</text>
            <text x="780" y="94" style="fill: var(--boost)">通過</text>
          </g>
          <g stroke-width="1.25">
            <rect x="190" y="124" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
            <rect x="360" y="124" width="160" height="52" rx="3" fill="none" stroke="currentColor" stroke-dasharray="4 3" style="color: var(--suppress)" />
            <rect x="530" y="124" width="160" height="52" rx="3" fill="none" stroke="currentColor" stroke-dasharray="4 3" style="color: var(--suppress)" />
            <rect x="700" y="124" width="160" height="52" rx="3" fill="none" stroke="currentColor" stroke-dasharray="4 3" style="color: var(--suppress)" />
          </g>
          <g class="s-label" font-size="13" text-anchor="middle">
            <text x="270" y="156" style="fill: var(--boost)">通過</text>
            <text x="440" y="156" style="fill: var(--suppress)">除外</text>
            <text x="610" y="156" style="fill: var(--suppress)">除外</text>
            <text x="780" y="156" style="fill: var(--suppress)">除外</text>
          </g>
          <g stroke-width="1.25">
            <rect x="190" y="186" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
            <rect x="360" y="186" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
            <rect x="530" y="186" width="160" height="52" rx="3" fill="none" stroke="currentColor" stroke-dasharray="4 3" style="color: var(--suppress)" />
            <rect x="700" y="186" width="160" height="52" rx="3" class="stroke" style="color: var(--boost)" />
          </g>
          <g class="s-label" font-size="13" text-anchor="middle">
            <text x="270" y="218" style="fill: var(--boost)">通過</text>
            <text x="440" y="218" style="fill: var(--boost)">通過</text>
            <text x="610" y="218" style="fill: var(--suppress)">除外</text>
            <text x="780" y="218" style="fill: var(--boost)">通過</text>
          </g>
          <text class="s-mono muted" x="190" y="258" font-size="10">実線 = 通過 ／ 破線 = 候補集合から除外</text>
        </svg>
      </div>
      <figcaption>
        <b>フォロー外へ届くのは単独ポストだけ。</b>フォロー外のリプライ・リポストは丸ごと落ちる。
        祖先を辿れないリプライはフォロー内でも落ちる。
        フォロー判定が付かなかった候補（<code>None</code>）はフォロー内と同じ扱いで通る —
        <b>ここは「不明なら通す」側に倒れている</b>。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">定義</p><h2>{N_FIL} 個それぞれ</h2></div>
    <div class="legend">
      <span><span class="chip author">投稿者</span> 投稿の作り方・内容で結果が変わる</span>
      <span><span class="chip viewer">閲覧者</span> 見る人の設定・履歴で決まる</span>
      <span><span class="chip system">運用</span> 実験・整合・安全のため</span>
    </div>
    {comp_table('main', 'filter', show_ctl=True)}
  </section>

  <section>
    <div><p class="eyebrow">深堀り</p><h2>安全側の倒し方が場所によって違う</h2></div>
    <p>
      属性が取れなかったとき、落とすか通すかは統一されていない。
      経過時間を計算できない候補は<b>落とす</b>側に倒れ、フォロー判定が付かない候補は<b>通す</b>側に倒れる。
      どちらも意図的な選択に見えるが、判断が分かれていること自体は読み取れる事実として残る。
    </p>
    <div class="callout">
      次は <a href="{url('scoring')}">採点</a>。
      ここを生き残った候補に、ようやく点数が付く。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ 画報 4: 採点
SCORING = header(
    '採点',
    '生き残った候補に点数が付く。ただし点数の材料は<b>実際に付いた反応ではなく、'
    'モデルが予測した「起きそうな確率」</b>のほう。',
    'scoring') + f"""

  <section>
    <div><p class="eyebrow">概念</p><h2>予測してから、重みを掛ける</h2></div>
    <p>
      直感的には「いいねが多い投稿ほど高得点」に思える。実際は違う。
      まず<b>モデルが「この人はこの投稿にいいねしそうか」をアクション別に予測</b>し、
      その確率に<b>アクションごとの重みを掛けて足す</b>。最後にもう一段別のモデルが再採点する。
    </p>
    <p>
      だから重みの表は「どの反応が何点」ではなく、
      <b>「どの反応が起きそうだと予測されたら、何点ぶん価値があると見なすか」</b>の表。
      同じ投稿でも、誰に見せるかで予測が変わり、点も変わる。
    </p>
  </section>

  <section>
    <div><p class="eyebrow">Input / Process / Output</p><h2>この段の入力と出力</h2></div>
    <figure>
      <div class="canvas">
        {ipo_svg(4,
                 ('生き残った候補', 'フィルタを通過したもの'),
                 f'{N_SCO} 段のスコアラーを順に適用する',
                 ['外部モデルがアクション別の確率を予測する',
                  '予測値に重みを掛けて 1 本のスコアにする',
                  '同じ著者の連続とフォロー外に減衰を掛ける',
                  '2 段目の外部モデルが再採点する'],
                 ('スコア付き候補', '並べ替えの基準ができた状態'),
                 '2 段目の呼び出しに失敗した場合は、重み付き和の結果をそのまま使う。')}
      </div>
      <figcaption>
        この段も候補を減らさない。<b>順序を決めるための数値を足すだけ</b>。
        減るのは次の段。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図 1</p><h2>採点は {N_SCO} 段。重みは真ん中で掛かる</h2></div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 900 220" role="img" aria-label="採点の 3 段。外部モデルがアクション別の確率を予測し、重み付き和で 1 本のスコアにし、2 段目のモデルが再採点する">
          <defs>
            <marker id="sc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <g class="stroke" stroke-width="1.25">
            <rect x="20" y="60" width="230" height="76" rx="3" />
            <rect x="320" y="60" width="230" height="76" rx="3" style="color: var(--accent)" stroke-width="1.75" />
            <rect x="620" y="60" width="230" height="76" rx="3" />
          </g>
          <g class="s-label" font-size="13" text-anchor="middle" fill="currentColor">
            <text x="135" y="88">確率を予測する</text>
            <text x="735" y="88">もう一度採点する</text>
          </g>
          <text class="s-label" x="435" y="88" text-anchor="middle" font-size="13" style="fill: var(--accent)">重みを掛けて足す</text>
          <g class="s-mono muted" font-size="10" text-anchor="middle">
            <text x="135" y="106">PhoenixScorer</text>
            <text x="435" y="106">RankingScorer</text>
            <text x="735" y="106">VMRanker</text>
          </g>
          <g class="s-label muted" font-size="10.5" text-anchor="middle">
            <text x="135" y="124">外部モデル</text>
            <text x="435" y="124">下の配点表がここで効く</text>
            <text x="735" y="124">外部モデル（2 段目）</text>
          </g>
          <g class="stroke" stroke-width="1.25" marker-end="url(#sc)">
            <line x1="250" y1="98" x2="316" y2="98" />
            <line x1="550" y1="98" x2="616" y2="98" />
          </g>
          <g class="s-mono" font-size="10" text-anchor="middle" style="fill: var(--gate)">
            <text x="283" y="86">アクション別の</text>
            <text x="283" y="102">予測確率</text>
            <text x="583" y="96">1 本のスコア</text>
          </g>
          <text class="s-label" x="20" y="176" font-size="12.5" style="fill: var(--gate)">配点が掛かるのはこの予測確率であって、実際に付いた反応の数ではない</text>
          <text class="s-label muted" x="20" y="200" font-size="11.5">実測のいいね数は前段で取得済みだが、スコア式に直接は入らない</text>
        </svg>
      </div>
      <figcaption>
        <b>「いいねが 100 件付いたから 50 点」ではない。</b>
        モデルの予測に重みが掛かる。予測モデル自体は公開されていないので、
        <b>何が予測を動かすのかはコードからは追えない</b>。
      </figcaption>
    </figure>
  </section>

  <section>
    <div>
      <p class="eyebrow">図 2</p>
      <p class="q">どの反応がいちばん重く扱われている？</p>
      <h2>加点は最大 20、減点は最大 −234</h2>
    </div>
    <p>
      横軸は対数目盛り。そうしないと通報の −234.0 以外がすべて潰れて見えない。
      その潰れること自体が、この表のいちばんの結論。
    </p>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 980 434" role="img" aria-label="行動ごとのスコア重みの既定値。リンクコピー共有が 20、返信と引用が 5、いいねが 0.5 なのに対し、通報は マイナス 234、ミュートは マイナス 58.8">
          <g class="stroke faint" stroke-width="1">
            <line x1="255" y1="36" x2="255" y2="398" stroke-dasharray="2 4" />
            <line x1="400" y1="36" x2="400" y2="398" stroke-dasharray="2 4" />
            <line x1="712" y1="36" x2="712" y2="398" stroke-dasharray="2 4" />
          </g>
          <g class="s-num muted" font-size="10" text-anchor="middle" fill="currentColor">
            <text x="255" y="424">−100</text>
            <text x="400" y="424">−10</text>
            <text x="556" y="424">0</text>
            <text x="712" y="424">+10</text>
          </g>
          <line x1="556" y1="34" x2="556" y2="400" class="stroke" stroke-width="1.5" />
          <g style="color: var(--boost)">
            <rect x="556" y="46"  width="198" height="12" fill="currentColor" />
            <rect x="556" y="68"  width="117" height="12" fill="currentColor" />
            <rect x="556" y="90"  width="117" height="12" fill="currentColor" />
            <rect x="556" y="112" width="117" height="12" fill="currentColor" />
            <rect x="556" y="134" width="72"  height="12" fill="currentColor" />
            <rect x="556" y="156" width="45"  height="12" fill="currentColor" />
            <rect x="556" y="178" width="26"  height="12" fill="currentColor" />
            <rect x="556" y="200" width="22"  height="12" fill="currentColor" />
            <rect x="556" y="222" width="12"  height="12" fill="currentColor" />
          </g>
          <g class="stroke muted" stroke-width="1.5">
            <line x1="553" y1="244" x2="559" y2="256" />
            <line x1="553" y1="266" x2="559" y2="278" />
          </g>
          <g style="color: var(--suppress)">
            <rect x="555" y="288" width="1"   height="12" fill="currentColor" />
            <rect x="330" y="310" width="226" height="12" fill="currentColor" />
            <rect x="309" y="332" width="247" height="12" fill="currentColor" />
            <rect x="290" y="354" width="266" height="12" fill="currentColor" />
            <rect x="200" y="376" width="356" height="12" fill="currentColor" />
          </g>
          <g class="s-label" font-size="12.5" text-anchor="end" fill="currentColor">
            <text x="182" y="56">リンクをコピーして共有</text>
            <text x="182" y="78">返信</text>
            <text x="182" y="100">引用</text>
            <text x="182" y="122">DM で共有</text>
            <text x="182" y="144">共有</text>
            <text x="182" y="166">リポスト</text>
            <text x="182" y="188">いいね</text>
            <text x="182" y="210">クリック</text>
            <text x="182" y="232">リンク遷移</text>
            <text x="182" y="254" class="muted">プロフィールクリック</text>
            <text x="182" y="276" class="muted">滞在</text>
            <text x="182" y="298" class="muted">滞在しなかった</text>
            <text x="182" y="320">ブロック</text>
            <text x="182" y="342">興味がない</text>
            <text x="182" y="364">ミュート</text>
            <text x="182" y="386">通報</text>
          </g>
          <g class="s-num" font-size="12" text-anchor="end">
            <text x="970" y="56"  style="fill: var(--boost)">20.0</text>
            <text x="970" y="78"  style="fill: var(--boost)">5.0</text>
            <text x="970" y="100" style="fill: var(--boost)">5.0</text>
            <text x="970" y="122" style="fill: var(--boost)">5.0</text>
            <text x="970" y="144" style="fill: var(--boost)">2.0</text>
            <text x="970" y="166" style="fill: var(--boost)">1.0</text>
            <text x="970" y="188" style="fill: var(--boost)">0.5</text>
            <text x="970" y="210" style="fill: var(--boost)">0.4</text>
            <text x="970" y="232" style="fill: var(--boost)">0.2</text>
            <text x="970" y="254" class="muted" fill="currentColor">0.0</text>
            <text x="970" y="276" class="muted" fill="currentColor">0.0</text>
            <text x="970" y="298" style="fill: var(--suppress)">−0.02</text>
            <text x="970" y="320" style="fill: var(--suppress)">−31.2</text>
            <text x="970" y="342" style="fill: var(--suppress)">−43.2</text>
            <text x="970" y="364" style="fill: var(--suppress)">−58.8</text>
            <text x="970" y="386" style="fill: var(--suppress)">−234.0</text>
          </g>
          <g class="stroke" stroke-width="1" stroke-dasharray="3 3" style="color: var(--boost)">
            <path d="M 673 74 L 800 74" />
          </g>
          <text class="s-label" x="806" y="70" font-size="11" style="fill: var(--boost)">相互フォロー相手なら</text>
          <text class="s-num" x="806" y="85" font-size="11" style="fill: var(--boost)">+15.0</text>
        </svg>
      </div>
      <figcaption>
        <b>通報 1 件は、いいね 468 件分の加点を打ち消す計算になる。</b>
        コード中のコメントは、この重み付けが「ネガティブな反応は全体として稀」という前提に立つと明記している。
        煽って反応を集める戦略は、期待値の設計上もともと割に合わない。
        <b>プロフィールクリックと滞在の既定値は 0.0</b> — 既定のままではスコアに寄与しない。
      </figcaption>
    </figure>
    <div class="callout">
      <b>ここに出てくる数値はすべてコード上の既定値。</b>
      本番で稼働している値ではない。種類ごとの大小関係は設計の意図として読めるが、
      「この重みだから何倍伸びる」はコードからは導けない。
    </div>
  </section>

  <section>
    <div><p class="eyebrow">定義</p><h2>{N_SCO} 段それぞれ</h2></div>
    {comp_table('main', 'scorer')}
  </section>

  <section>
    <div><p class="eyebrow">深堀り</p><h2>読み違えやすいところ</h2></div>
    <div class="split">
      <div class="panel can">
        <h3>コードから言える</h3>
        <ul>
          <li>返信・引用の既定重みは、いいねの 10 倍</li>
          <li>リンクをコピーしての共有が最も重い（20.0）</li>
          <li>相互フォロー相手からの返信には大きなブーストが乗る</li>
          <li>ネガティブは 1〜2 桁重い</li>
        </ul>
      </div>
      <div class="panel cannot">
        <h3>言えないこと</h3>
        <ul>
          <li>これらが本番で使われている値かどうか</li>
          <li>予測モデルが何を見て確率を出しているか</li>
          <li>2 段目の再採点で順位がどう変わるか</li>
        </ul>
      </div>
    </div>
    <div class="callout">
      次は <a href="{url('selection')}">選択と出口</a>。点が付いたので、あとは並べて切るだけ。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ 画報 5: 選択と出口
SELECTION = header(
    '選択と出口',
    'スコア順に並べて切る。<b>切ったあとにもう 1 本フィルタ列がある</b>ので、'
    '返る件数は上限より少なくなりうる。',
    'selection') + f"""

  <section>
    <div><p class="eyebrow">概念</p><h2>切ってから、重い処理をする</h2></div>
    <p>
      並べ替えて上位を取る、で終わりではない。この段は
      <b>「上位 50 に切る → 重い情報を足す → 安全性で落とす → 35 に切る」</b>という順序になっている。
    </p>
    <p>
      なぜ 2 回切るのか。<b>可視性の判定は高コスト</b>なので、候補全部にはかけたくない。
      先に 50 件へ絞ってからかけ、そこで落ちた分を見込んで最終的に 35 件へ切る。
      <b>絞り込みが 2 段あるのは、選択後に減ることを織り込んでいるから</b>。
    </p>
  </section>

  <section>
    <div><p class="eyebrow">Input / Process / Output</p><h2>この段の入力と出力</h2></div>
    <figure>
      <div class="canvas">
        {ipo_svg(5,
                 ('スコア付き候補', '順序を決める数値を持っている'),
                 'セレクタと選択後の {N_PS_HYD + N_PS_FIL} 部品を適用する',
                 ['スコア降順に並べて上位 50 件を選ぶ',
                  f'選択後ハイドレータ {N_PS_HYD} 個が情報を足す',
                  f'選択後フィルタ {N_PS_FIL} 個が可視性で落とす',
                  '最終的に 35 件へ切る'],
                 ('外側へ渡す投稿', '35 件以下。ここが内側の出口'),
                 'スコアが無い候補は負の無限大として扱われ、最後尾に落ちる。')}
      </div>
      <figcaption>
        ここが<b>内側のパイプラインの出口</b>。この先は外側が受け取り、
        広告やおすすめユーザーを混ぜて最大 47 件のレスポンスにする。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図</p><h2>50 → 選択後 {N_PS_HYD + N_PS_FIL} 部品 → 35</h2></div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 900 200" role="img" aria-label="上位 50 件を選んだ後に {N_PS_HYD} 個のハイドレータと {N_PS_FIL} 個のフィルタが走り、最後に 35 件へ切られる流れ">
          <defs>
            <marker id="se" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <g class="stroke" stroke-width="1.25">
            <rect x="20" y="56" width="150" height="66" rx="3" />
            <rect x="250" y="56" width="180" height="66" rx="3" />
            <rect x="510" y="56" width="180" height="66" rx="3" />
            <rect x="770" y="56" width="110" height="66" rx="3" />
          </g>
          <g class="s-label" font-size="12.5" text-anchor="middle" fill="currentColor">
            <text x="95" y="82">上位 50 を選ぶ</text>
            <text x="340" y="82">情報を足す</text>
            <text x="600" y="82">安全性で落とす</text>
            <text x="825" y="82">35 件に切る</text>
          </g>
          <g class="s-mono muted" font-size="10" text-anchor="middle">
            <text x="95" y="100">TopKScoreSelector</text>
            <text x="340" y="100">post_selection_hydrators</text>
            <text x="600" y="100">post_selection_filters</text>
            <text x="825" y="100">result_size</text>
          </g>
          <g class="s-label muted" font-size="10.5" text-anchor="middle">
            <text x="340" y="116">{N_PS_HYD} 個</text>
            <text x="600" y="116">{N_PS_FIL} 個</text>
          </g>
          <g class="stroke" stroke-width="1.25" marker-end="url(#se)">
            <line x1="170" y1="89" x2="246" y2="89" />
            <line x1="430" y1="89" x2="506" y2="89" />
            <line x1="690" y1="89" x2="766" y2="89" />
          </g>
          <text class="s-label" x="20" y="164" font-size="12" style="fill: var(--gate)">ここで落ちた分だけ、返る件数は 35 より少なくなりうる</text>
        </svg>
      </div>
      <figcaption>
        選択後のフィルタは可視性（安全性ラベル）と会話の重複排除。
        <b>いずれも運用側の都合で、投稿者からも閲覧者の設定からも動かせない。</b>
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">定義</p><h2>セレクタ</h2></div>
    {comp_table('main', 'selector')}
    <div><p class="eyebrow">定義</p><h2>選択後のハイドレータ {N_PS_HYD} 個</h2></div>
    {comp_table('post_selection', 'hydrator')}
    <div><p class="eyebrow">定義</p><h2>選択後のフィルタ {N_PS_FIL} 個</h2></div>
    {comp_table('post_selection', 'filter')}
  </section>

  <section>
    <div><p class="eyebrow">深堀り</p><h2>外側に出たあと</h2></div>
    <p>
      ここまでが内側。外側の For You パイプラインは、この 35 件以下の投稿を
      1 つの候補ソースとして受け取り、広告・おすすめユーザー・プロンプト・フレームを混ぜて
      <b>最大 47 件</b>のレスポンスを作る。件数が増えるのは、投稿以外が差し込まれるため。
    </p>
    <div class="callout">
      47 の内訳を「投稿 35 + モジュール 4 + フレーム 8」と読むのは<b>誤り</b>。
      35 は投稿と広告を混ぜた列の長さで、モジュール枠 4 に対応する配線はコードに見当たらない。
      全体の流れは <a href="{url('hub')}">For You の通り道</a> を参照。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ メタ: 根拠台帳のしくみ
LEDGER_BODY = f"""  <header>
    <p class="eyebrow">xai-org/x-algorithm · a389166f</p>
    <h1>根拠台帳のしくみ</h1>
    <p class="lede">
      2,015 ファイルを相手にした解析の主な失敗は、<b>読んだつもりでそれらしい要約を書くこと</b>。
      出力を見ても区別がつかないので、機械で潰すしかない。
    </p>
    {series_nav(None)}
  </header>

  <section>
    <div>
      <p class="eyebrow">図 1</p>
      <p class="q">ここに書いてある数字は、どこまで信用できる？</p>
      <h2>行番号と実文字列まで固定して照合している</h2>
    </div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 900 176" role="img" aria-label="source.lock でコミットを固定し、取得したコードと台帳の行と文字列を照合し、一致しなければ検証が失敗する流れ">
          <defs>
            <marker id="ld" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <g class="stroke" stroke-width="1.25">
            <rect x="10" y="42" width="170" height="60" rx="3" />
            <rect x="240" y="42" width="170" height="60" rx="3" />
            <rect x="470" y="42" width="170" height="60" rx="3" />
            <rect x="700" y="42" width="170" height="60" rx="3" />
          </g>
          <g class="s-mono" font-size="11.5" text-anchor="middle">
            <text x="95" y="68">source.lock</text>
            <text x="325" y="68">vendor/</text>
            <text x="555" y="68">*.yaml</text>
            <text x="785" y="68">make verify</text>
          </g>
          <g class="s-label muted" font-size="10.5" text-anchor="middle">
            <text x="95" y="86">commit を固定</text>
            <text x="325" y="86">その commit だけ取得</text>
            <text x="555" y="86">path : line : snippet</text>
            <text x="785" y="86">実ファイルと照合</text>
          </g>
          <g class="stroke" stroke-width="1.25" marker-end="url(#ld)">
            <line x1="180" y1="72" x2="237" y2="72" />
            <line x1="410" y1="72" x2="467" y2="72" />
            <line x1="640" y1="72" x2="697" y2="72" />
          </g>
          <g class="s-mono muted" font-size="9.5" text-anchor="middle">
            <text x="208" y="65">SHA 照合</text>
            <text x="438" y="65">参照</text>
            <text x="668" y="65">{EVIDENCE_TOTAL} 件</text>
          </g>
          <g class="stroke" stroke-width="1" stroke-dasharray="3 3">
            <line x1="785" y1="102" x2="785" y2="126" />
          </g>
          <text class="s-label" x="785" y="142" text-anchor="middle" font-size="11.5" style="fill: var(--suppress)">1 件でも違えば exit 1</text>
          <text class="s-mono muted" x="785" y="158" text-anchor="middle" font-size="9.5">緑でなければ主張として出さない</text>
        </svg>
      </div>
      <figcaption>
        台帳のエントリは必ず「ファイルのどこに、どんな文字列が実在するか」を持つ。
        <b>snippet を書き写した＝実際にその行を開いた</b>が構造的に強制される。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">図 2</p><h2>台帳は 3 本、照合は 1 つ</h2></div>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 880 230" role="img" aria-label="3 本の台帳がスキーマは異なるが、evidence の照合は共通の関数 1 つを通ることを示す図">
          <defs>
            <marker id="le" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <g class="stroke" stroke-width="1.25">
            <rect x="20" y="28" width="250" height="48" rx="3" />
            <rect x="20" y="90" width="250" height="48" rx="3" />
            <rect x="20" y="152" width="250" height="48" rx="3" />
            <rect x="560" y="90" width="290" height="48" rx="3" style="color: var(--boost)" />
          </g>
          <g class="s-mono" font-size="11.5">
            <text x="36" y="50">factors.yaml</text>
            <text x="36" y="112">code.yaml</text>
            <text x="36" y="174">components.yaml</text>
          </g>
          <g class="s-label muted" font-size="10">
            <text x="36" y="66">投稿者が操作できる要因 — {len(FACTORS)} 件</text>
            <text x="36" y="128">コードそのものの観察 — {len(CODE)} 件</text>
            <text x="36" y="190">配線された部品 — {len(COMPONENTS)} 件</text>
          </g>
          <text class="s-mono" x="705" y="112" text-anchor="middle" font-size="12" style="fill: var(--boost)">check_evidence()</text>
          <text class="s-label" x="705" y="130" text-anchor="middle" font-size="10.5" style="fill: var(--boost)">照合はこの 1 箇所だけ</text>
          <g class="stroke faint" stroke-width="1.25" marker-end="url(#le)">
            <path d="M 270 52 L 420 52 L 420 108 L 556 108" />
            <path d="M 270 114 L 556 114" />
            <path d="M 270 176 L 420 176 L 420 120 L 556 120" />
          </g>
          <text class="s-label muted" x="20" y="222" font-size="11">スキーマは 3 本とも違うが、根拠の厳しさは共通。台帳を足すときに書くのは定義 1 つだけ。</text>
        </svg>
      </div>
      <figcaption>
        台帳ごとに照合を書き分けると、<b>緩いほうが抜け道になる</b>。
        3 本目を足したときの実際の差分は定義 25 行で、照合の関数は 1 行も変えていない。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">実演</p><h2>壊すと落ちることを確かめてある</h2></div>
    <p>緑になることは検証の証拠にならない。わざと壊して落ちることまで確認して初めて意味がある。</p>
    <div class="tablewrap">
      <table>
        <thead><tr><th>壊し方</th><th>結果</th></tr></thead>
        <tbody>
          <tr><td>snippet を 1 文字変える</td><td>exit 1（期待値と実際の行を両方表示）</td></tr>
          <tr><td>存在しない行番号を指す</td><td>exit 1（<code>param.rs は 1084 行しかない</code>）</td></tr>
          <tr><td>台帳の commit を別の値にする</td><td>exit 1（<code>source.lock</code> と不一致）</td></tr>
          <tr><td>取得したコードを消す</td><td>exit 1（「検証できなかった」を成功に倒さない）</td></tr>
          <tr><td>部品を 1 個消す</td><td>exit 1（配線順の欠番として検出）</td></tr>
          <tr><td>配線順を重複させる</td><td>exit 1</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <div><p class="eyebrow">実績</p><h2>実際に何度も間違いを拾った</h2></div>
    <div class="tablewrap">
      <table>
        <thead><tr><th>書いてしまった誤り</th><th>実態</th></tr></thead>
        <tbody>
          <tr><td>行番号が 1 行ずれていた</td><td>投入直後に照合が検出（散文なら誰も気づかない）</td></tr>
          <tr><td>「ハッシュで擬似ランダムに振り分け」</td><td>乗数が奇数なので、実体は ID の偶奇分割だった</td></tr>
          <tr><td>「max_age の実値は確定できない」</td><td>48 時間として定義され、配線箇所も公開されていた</td></tr>
          <tr><td>「For You は 2800 件を受け取る」</td><td>別系統の定数。ここでパイプラインの入れ子構造が判明した</td></tr>
          <tr><td>フィルタ 16 個</td><td>数え落としで 17 個</td></tr>
          <tr><td>「投稿 35 枠 + モジュール 4 枠」</td><td>35 は投稿と広告を混ぜた列の長さ。配分の根拠はコードに無い</td></tr>
          <tr><td>ハイドレータ 12 個の欠落</td><td>段が丸ごと抜けたカタログになっていた</td></tr>
        </tbody>
      </table>
    </div>
    <div class="callout">
      <b>台帳に書けない主張は、この資料では主張しない。</b>
      grep がヒットしただけ、ファイル名から推測しただけの段階では載せない。
      開いて読み、その行の実文字列を書き写したものだけが載る。
    </div>
  </section>

{FOOT}"""


# ═══════════════════════════ 索引: 内側の部品表
PARTS_BODY = f"""  <header>
    <p class="eyebrow">xai-org/x-algorithm · a389166f</p>
    <h1>内側の部品表</h1>
    <p class="lede">
      内側のパイプラインに配線された <b>{len(COMPONENTS)} 個の部品</b>を 1 枚に並べた一覧。
      段ごとの解説は連載のほうにある。
    </p>
    {series_nav(None)}
  </header>

  <section>
    <div><p class="eyebrow">使い方</p><h2>横断で引くための表</h2></div>
    <p>
      各部品が何をするかは段ごとの資料で説明している。ここは
      <b>「あの名前はどこの段だったか」を引く</b>ための一覧。
      配線順は <code>stage × kind</code> ごとに 1 始まりの連番で、機械検証されている。
    </p>
    <div class="legend">
      <span><span class="chip author">投稿者</span> 投稿の作り方・内容で結果が変わる</span>
      <span><span class="chip viewer">閲覧者</span> 見る人の設定・履歴で決まる</span>
      <span><span class="chip system">運用</span> 実験・整合・安全のため</span>
    </div>
  </section>

  <section>
    <div><p class="eyebrow">1</p><h2>候補ソース（{n('main', 'source')}）</h2></div>
    {comp_table('main', 'source', show_ctl=True)}
    <p><a href="{url('sources')}">→ 候補ソースの解説</a></p>
  </section>

  <section>
    <div><p class="eyebrow">2</p><h2>ハイドレータ（{n('main', 'hydrator')}）</h2></div>
    {comp_table('main', 'hydrator', show_ctl=True)}
    <p><a href="{url('hydrators')}">→ ハイドレータの解説</a></p>
  </section>

  <section>
    <div><p class="eyebrow">3</p><h2>フィルタ（{n('main', 'filter')}）</h2></div>
    {comp_table('main', 'filter', show_ctl=True)}
    <p><a href="{url('filters')}">→ フィルタの解説</a></p>
  </section>

  <section>
    <div><p class="eyebrow">4</p><h2>スコアラー（{n('main', 'scorer')}）</h2></div>
    {comp_table('main', 'scorer', show_ctl=True)}
    <p><a href="{url('scoring')}">→ 採点の解説</a></p>
  </section>

  <section>
    <div><p class="eyebrow">5</p><h2>セレクタと選択後（{n('main', 'selector') + n('post_selection', 'hydrator') + n('post_selection', 'filter')}）</h2></div>
    {comp_table('main', 'selector', show_ctl=True)}
    {comp_table('post_selection', 'hydrator', show_ctl=True)}
    {comp_table('post_selection', 'filter', show_ctl=True)}
    <p><a href="{url('selection')}">→ 選択と出口の解説</a></p>
  </section>

{FOOT}"""


# ═══════════════════════════ ハブ
HUB_BODY = f"""  <header>
    <p class="eyebrow">xai-org/x-algorithm · a389166f</p>
    <h1>For You の通り道</h1>
    <p class="lede">
      X が For You タイムラインの中核コードを Apache-2.0 で公開した。
      これはそのコードを読んで、<b>1 本の投稿がタイムラインに並ぶまでに何を通るのか</b>を図にしたもの。
      段ごとの詳細は下の資料に分けてある。
    </p>
  </header>

  <section>
    <div><p class="eyebrow">はじめに</p><h2>何のための資料か</h2></div>
    <p>
      公開されたのは 2,015 ファイル・4 言語のコードで、そのままでは「自分の投稿がどう扱われるのか」は読み取れない。
      かといって「X で伸ばすコツ」の類は、根拠がコードのどこにあるのか示さない。
    </p>
    <p>
      これはその間を埋めるためのもの。<b>投稿の扱われ方を決めている処理だけを抜き出し、
      それぞれ「コードのどのファイルの何行目にそう書いてあるか」まで固定したうえで作図している。</b>
      主張はすべて機械照合を通っていて、コードとズレたら検証が落ちる。
    </p>
    <div class="split">
      <div class="panel can">
        <h3>答えられること</h3>
        <ul>
          <li>候補はたくさんあるのに、実際に並ぶのがごく少数なのはなぜか</li>
          <li>フォロー外の人に届く投稿と、届かない投稿は何が違うのか</li>
          <li>コード上、どの反応がどれだけ重く扱われているのか</li>
        </ul>
      </div>
      <div class="panel cannot">
        <h3>答えられないこと</h3>
        <ul>
          <li>この投稿は伸びるか — 本番の設定値・学習済みモデル・利用者ごとの特徴量は公開されていない</li>
          <li>何点取れば表示されるか — 閾値はコードに書かれていない</li>
          <li>自分の投稿がなぜ伸びなかったか — 個別の配信結果はこのコードからは追えない</li>
        </ul>
      </div>
    </div>
  </section>

  <section>
    <div>
      <p class="eyebrow">全体像</p>
      <p class="q">候補ソースはたくさんあるのに、実際に並ぶのはごく少数。どこで減っている？</p>
      <h2>減らしているのは内側のパイプライン。外側は混ぜるだけ</h2>
    </div>
    <p>
      For You は 1 本の処理ではなく、<b>パイプラインが 2 段に入れ子</b>になっている。
      投稿候補を集めて落として採点して絞る仕事は内側で完結し、
      外側は絞り込み済みの投稿に広告やおすすめユーザーを混ぜて返すだけ。
    </p>
    <figure>
      <div class="canvas">
        <svg viewBox="0 0 1000 372" role="img" aria-label="For You パイプラインの内側に Phoenix 候補パイプラインが入れ子になっており、7 つのソースから集めた候補が 17 個のフィルタと採点を経て上位 50 件、さらに 35 件に絞られ、外側で他のソースと混ぜて最大 47 件になる図">
          <defs>
            <marker id="hb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="currentColor" />
            </marker>
          </defs>
          <rect x="8" y="46" width="984" height="296" rx="5" class="stroke faint" stroke-width="1.25" />
          <text class="s-mono muted" x="20" y="36" font-size="10.5">外側 — For You パイプライン</text>
          <rect x="28" y="78" width="668" height="206" rx="4" class="stroke" stroke-width="1.25" />
          <text class="s-mono" x="40" y="98" font-size="10.5" style="fill: var(--accent)">内側 — Phoenix 候補パイプライン</text>
          <text class="s-label muted" x="40" y="113" font-size="10">ScoredPostsSource がこれを丸ごと 1 本実行する</text>
          <polygon points="48,128 676,180 676,216 48,268" fill="currentColor" opacity="0.09" />
          <polyline points="48,128 676,180" class="stroke muted" stroke-width="1" />
          <polyline points="48,268 676,216" class="stroke muted" stroke-width="1" />
          <g class="stroke faint" stroke-width="1" stroke-dasharray="3 4">
            <line x1="172" y1="138" x2="172" y2="258" />
            <line x1="296" y1="148" x2="296" y2="249" />
            <line x1="420" y1="158" x2="420" y2="239" />
            <line x1="548" y1="169" x2="548" y2="229" />
          </g>
          <g class="s-label" font-size="12.5" text-anchor="middle" fill="currentColor">
            <text x="110" y="194">7 ソース</text>
            <text x="234" y="194">17 フィルタ</text>
            <text x="358" y="194">採点</text>
            <text x="484" y="196">上位 50</text>
            <text x="612" y="196">35 件</text>
          </g>
          <g class="s-mono muted" font-size="9.5" text-anchor="middle">
            <text x="110" y="212">1 本で最大 800</text>
            <text x="234" y="212">1 つでも落ちたら終わり</text>
            <text x="358" y="212">重み付き和</text>
            <text x="484" y="213">スコア降順</text>
            <text x="612" y="213">result_size</text>
          </g>
          <text class="s-mono" x="234" y="300" text-anchor="middle" font-size="10" style="fill: var(--gate)">ここを通過した実数はコードに無い</text>
          <g class="stroke" stroke-width="1" stroke-dasharray="3 3" style="color: var(--gate)">
            <line x1="234" y1="268" x2="234" y2="288" />
          </g>
          <line x1="696" y1="198" x2="742" y2="198" class="stroke" stroke-width="1.25" marker-end="url(#hb)" />
          <text class="s-mono muted" x="719" y="191" text-anchor="middle" font-size="9.5">35</text>
          <rect x="748" y="150" width="150" height="96" rx="3" class="stroke" stroke-width="1.25" />
          <text class="s-label" x="823" y="176" text-anchor="middle" font-size="12">混ぜる</text>
          <g class="s-label muted" font-size="10" text-anchor="middle">
            <text x="823" y="196">＋ 広告</text>
            <text x="823" y="211">＋ おすすめユーザー</text>
            <text x="823" y="226">＋ プロンプト / フレーム</text>
          </g>
          <line x1="898" y1="198" x2="924" y2="198" class="stroke" stroke-width="1.25" marker-end="url(#hb)" />
          <rect x="928" y="176" width="58" height="44" rx="22" class="stroke faint" stroke-width="1.25" />
          <text class="s-num" x="957" y="196" text-anchor="middle" font-size="14" fill="currentColor">47</text>
          <text class="s-mono muted" x="957" y="211" text-anchor="middle" font-size="9">最大</text>
        </svg>
      </div>
      <figcaption>
        <b>絞り込みは 2 段ある。</b>採点した候補からスコア上位 50 件を選び、そのあと <code>result_size</code> でさらに 35 件に切る。
        入口側は 1 ソースが最大 800 件を返すが、<b>7 ソース合計で何件になるかはコードに書かれていない</b>ので描いていない。
        中央の「17 フィルタ」を通過した実数も同じ理由で空白のまま。
      </figcaption>
    </figure>
  </section>

  <section>
    <div><p class="eyebrow">連載</p><h2>段ごとに 1 枚</h2></div>
    <p>
      内側の {len(SERIES)} つの段を、それぞれ <b>概念 → Input / Process / Output → 図 → 部品の定義 → 深堀り</b> の順で
      1 枚にまとめてある。上から順に読むと、候補が生まれてから出口に届くまでを追える。
    </p>
    <div class="cards">
      <a class="card" href="{url('sources')}">
        <span class="kicker">段 1 · Input</span>
        <span class="name">候補ソース</span>
        <span class="desc">{N_SRC} 本の網を同時に投げて候補を集める。うち {N_SRC_OFF} 本は既定で畳まれている。</span>
        <span class="meta">図 2 ／ 部品 {n('main', 'source')}</span>
      </a>
      <a class="card" href="{url('hydrators')}">
        <span class="kicker">段 2 · Enrich</span>
        <span class="name">ハイドレータ</span>
        <span class="desc">候補に身元を付ける。フィルタが見ているのは投稿ではなく、ここで貼られた属性。</span>
        <span class="meta">図 2 ／ 部品 {n('main', 'hydrator')}</span>
      </a>
      <a class="card" href="{url('filters')}">
        <span class="kicker">段 3 · Gate</span>
        <span class="name">フィルタ</span>
        <span class="desc">0 か 1 で落とす関門。投稿者が影響できるのは {N_FIL} 個中 {N_FIL_AUTHOR} 個だけ。</span>
        <span class="meta">図 3 ／ 部品 {n('main', 'filter')}</span>
      </a>
      <a class="card" href="{url('scoring')}">
        <span class="kicker">段 4 · Score</span>
        <span class="name">採点</span>
        <span class="desc">重みが掛かる相手は実測の反応数ではなく、モデルが予測した確率のほう。</span>
        <span class="meta">図 3 ／ 部品 {n('main', 'scorer')}</span>
      </a>
      <a class="card" href="{url('selection')}">
        <span class="kicker">段 5 · Output</span>
        <span class="name">選択と出口</span>
        <span class="desc">上位 50 に切ってから重い処理をかけ、最後に 35 件へ。切るのが 2 回ある理由。</span>
        <span class="meta">図 2 ／ 部品 {n('main', 'selector') + n('post_selection', 'hydrator') + n('post_selection', 'filter')}</span>
      </a>
      <a class="card" href="{url('parts')}">
        <span class="kicker">索引</span>
        <span class="name">内側の部品表</span>
        <span class="desc">{len(COMPONENTS)} 個の部品を 1 枚に並べた一覧。名前から段を引くための表。</span>
        <span class="meta">表 7 ／ 部品 {len(COMPONENTS)}</span>
      </a>
      <a class="card" href="{url('ledger')}">
        <span class="kicker">メタ</span>
        <span class="name">根拠台帳のしくみ</span>
        <span class="desc">なぜこの数字を信用してよいか。行番号と実文字列まで固定した照合と、壊して落ちることの実演。</span>
        <span class="meta">図 2 ／ 検証 {EVIDENCE_TOTAL} 件</span>
      </a>
    </div>
  </section>

  <section>
    <div>
      <p class="eyebrow">まとめ</p>
      <p class="q">結局、投稿する側から見て何が言える？</p>
      <h2>足切りは形式で決まり、点数は反応の種類で決まる</h2>
    </div>
    <div class="tablewrap">
      <table>
        <thead><tr><th>段</th><th>効き方</th><th>コードから言えること</th><th style="width:8em">詳細</th></tr></thead>
        <tbody>
          <tr>
            <td>入口</td><td>供給量</td>
            <td>候補を集めるのは 7 本のソース。1 本が返すのは最大 800〜1200 件で、合計の実数はコードに書かれていない。</td>
            <td><a href="{url('sources')}">候補ソース</a></td>
          </tr>
          <tr>
            <td>属性付け</td><td>材料</td>
            <td>フィルタが見ているのは投稿そのものではなく、この段で外部から取ってきて貼られた属性。</td>
            <td><a href="{url('hydrators')}">ハイドレータ</a></td>
          </tr>
          <tr>
            <td>フィルタ</td><td>0 か 1</td>
            <td>{N_FIL} 個が直列。フォロー外に届けたいならリプライやリポストではなく単独ポストである必要がある。重みでは補償できない。</td>
            <td><a href="{url('filters')}">フィルタ</a></td>
          </tr>
          <tr>
            <td>採点</td><td>加点</td>
            <td>既定値では返信・引用がいいねの 10 倍。外に持ち出される共有が最も重い。ただし掛かる相手は予測確率。</td>
            <td><a href="{url('scoring')}">採点</a></td>
          </tr>
          <tr>
            <td>採点</td><td>減点</td>
            <td>通報・ミュート・ブロックは加点より 1〜2 桁重い。1 件で多数の加点を打ち消しうる。</td>
            <td><a href="{url('scoring')}">採点</a></td>
          </tr>
          <tr>
            <td>出口</td><td>枠の数</td>
            <td>上位 50 件へ、さらに 35 件へと 2 段で切られる。外側で他の要素を混ぜて 1 レスポンス最大 47 件。</td>
            <td><a href="{url('selection')}">選択と出口</a></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

{FOOT}"""


PAGES = {
    'stage-sources.html': ('候補ソース', SOURCES),
    'stage-hydrators.html': ('ハイドレータ', HYDRATORS),
    'stage-filters.html': ('フィルタ', FILTERS),
    'stage-scoring.html': ('採点', SCORING),
    'stage-selection.html': ('選択と出口', SELECTION),
    'naigawa-no-buhinhyou.html': ('内側の部品表', PARTS_BODY),
    'konkyo-daichou.html': ('根拠台帳のしくみ', LEDGER_BODY),
    'for-you-no-toorimichi.html': ('For You の通り道', HUB_BODY),
}

PREVIEW = DIST / 'preview'
DIST.mkdir(exist_ok=True)
PREVIEW.mkdir(exist_ok=True)
for fname, (title, body) in PAGES.items():
    fragment = page(title, body)
    (DIST / fname).write_text(fragment, encoding='utf-8')
    (PREVIEW / fname).write_text(standalone(fragment), encoding='utf-8')
    print(f'  {fname:32} {title}')

print(f'\n台帳: factors={len(FACTORS)} code={len(CODE)} components={len(COMPONENTS)} '
      f'evidence={sum(len(e.get("evidence", [])) for e in FACTORS + CODE + COMPONENTS)}')

if _MISSING:
    for f in PAGES:
        (DIST / f).unlink(missing_ok=True)
        (DIST / 'preview' / f).unlink(missing_ok=True)
    sys.exit('NG: links.json に URL が無いキーが参照された: '
             + ', '.join(sorted(_MISSING))
             + '\n     リンク切れのページを出さないため、生成物を削除して中断した。')

print(f'出力: {DIST.relative_to(ROOT)}/ に {len(PAGES)} 枚'
      f'（ローカル閲覧用は {PREVIEW.relative_to(ROOT)}/）')
