"""solutions/*/*.json 취합·검증 → data/solutions_all.json + 보고."""
import json, glob, os, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db = {}
for k in ['m1', 'm2', 'prob']:
    for r in json.load(open(f'{ROOT}/data/{k}.json')):
        db[r['id']] = (k, r)
themes, sols, errs = [], {}, []
for f in sorted(glob.glob(f'{ROOT}/solutions/*/*.json')):
    try:
        t = json.load(open(f))
    except Exception as e:
        errs.append(f'JSON 오류 {f}: {e}'); continue
    cids = {c['id'] for c in t.get('core_concepts', [])}
    for need in ['theme', 'overview', 'core_concepts', 'decision_flow', 'solutions']:
        if need not in t: errs.append(f'{f}: {need} 없음')
    for s in t.get('solutions', []):
        sid = s.get('id')
        if sid not in db: errs.append(f'{f}: 알 수 없는 id {sid}'); continue
        if sid in sols: errs.append(f'중복 풀이 {sid}')
        r = db[sid][1]
        if r['theme']['primary'] != t['theme']: errs.append(f'{sid}: 테마 불일치 {t["theme"]}')
        if str(s.get('answer')) != str(r['answer']): errs.append(f'{sid}: 정답 불일치 풀이={s.get("answer")} DB={r["answer"]}')
        for fld in ['guide', 'solutions', 'supplement', 'skill_point']:
            if not s.get(fld): errs.append(f'{sid}: {fld} 비어 있음')
        txt = json.dumps(s, ensure_ascii=False)
        for sub in s.get('solutions', []):
            for st in sub.get('steps', []):
                if st.get('body', '').count('$') % 2: errs.append(f'{sid}: $ 짝 안 맞음 ({st.get("label")})')
        if s.get('needs_review'): errs.append(f'{sid}: needs_review → {s["needs_review"]}')
        sols[sid] = s
    t2 = {k: v for k, v in t.items() if k != 'solutions'}
    t2['problem_ids'] = [s['id'] for s in t.get('solutions', [])]
    themes.append(t2)
missing = sorted(set(db) - set(sols))
cnt = collections.Counter(db[i][0] for i in sols)
print('풀이 수', dict(cnt), '/ 전체', len(db), '/ 누락', len(missing))
if missing: print('누락:', missing if len(missing) < 40 else f'{len(missing)}건')
print('\n'.join(errs) or '오류 없음')
out = []
for i, (k, r) in db.items():
    if i in sols: out.append({**r, 'study_solution': sols[i]})
json.dump({'themes': themes, 'problems': out}, open(f'{ROOT}/data/solutions_all.json', 'w'), ensure_ascii=False, indent=1)
