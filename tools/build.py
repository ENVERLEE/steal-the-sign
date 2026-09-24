import json,glob,importlib.util,sys,os
S=os.path.dirname(os.path.abspath(__file__))
OUT=sys.argv[1] if len(sys.argv)>1 else S+'/out'
os.makedirs(OUT,exist_ok=True)
SUBJ={'m1':('수학Ⅰ','M1'),'m2':('수학Ⅱ','M2'),'prob':('확률과 통계','PS')}
EXAM={6:'6월 모의평가',9:'9월 모의평가',11:'대학수학능력시험'}
THEMES={
'm1':"거듭제곱근|지수로그의 연산|지수함수의 그래프|로그함수의 그래프|지수로그의 방정식과 부등식|지수함수와 로그함수의 대칭성|지수함수와 로그함수의 평행이동|곡선의 합동|삼각함수의 그래프|삼각함수의 방정식과 부등식|사인과 코사인의 관계|사인법칙과 코사인법칙|등차수열과 등비수열|등차수열의 합|등비수열의 합|여러 가지 수열의 합|귀납적으로 정의된 수열|수열의 활용|수학적 귀납법|역추적|가지수열",
'm2':"함수의 극한|도형에 대한 극한|극한값과 인수결정|함수의 연속|곱함수의 연속|미분계수와 미분법|미분가능성|접선의 활용|증가/감소, 극대/극소, 최대/최소|방정식에의 활용|함수의 그래프와 부등식|합성함수의 방정식|다항함수와 정수조건|적분 연산|정적분으로 정의된 함수|정적분으로 정의된 함수의 활용|정적분과 최대/최소|정적분과 넓이|위치, 속도, 가속도|적분구간의 평행이동|새롭게 정의된 함수",
'prob':"원순열|같은 것이 있는 순열|중복순열|이항정리와 이항계수|중복조합 - 부등식 기본형|중복조합 - 부등식 응용형|중복조합 - 합 기본형|중복조합 - 합 응용형|확률의 정의 Ⅰ|확률의 정의 Ⅱ|조건부확률 Ⅰ|조건부확률 Ⅱ|확률의 곱셈정리|독립시행의 확률|이산확률변수|연속확률변수|이항분포|정규분포와 표준화|정규분포곡선의 성질|이항분포와 정규분포의 관계|표본평균|모평균의 추정"}
THEMES={k:v.split('|') for k,v in THEMES.items()}
BEH={"계산","이해","추론","문제해결"}
REASON=["조건의 식 번역","경우 나누기","그래프·도형 해석","대칭성·주기성 활용","단순화·특수화로 규칙성 찾기","나열·역추적","치환·보조함수 도입","미지수 소거·연립","정수 조건으로 후보 좁히기","여사건·전체에서 빼기","대응·모델링"]
strat=json.load(open(S+'/strategy_notes.json'))
SIDS={i['id'] for i in strat['items']}
skel=json.load(open(S+'/skeleton.json'))
errors=[];allrec=[]
for k,(sname,pre) in SUBJ.items():
    src={int(a):b for a,b in (l.split() for l in open(f'{S}/sources_{k}.txt'))}
    sk={x['no']:x for x in skel[k]}
    recs={}
    for f in sorted(glob.glob(f'{S}/records/{k}_*.py')):
        spec=importlib.util.spec_from_file_location('r',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        for r in m.R:
            if r['no'] in recs: errors.append(f'{k} dup {r["no"]}')
            recs[r['no']]=r
    out=[]
    for no in sorted(sk):
        if no not in recs: errors.append(f'{k} missing {no}'); continue
        r=recs[no]; y,mo,num=map(int,src[no].split('-'))
        ay=y+1; code=f'{ay%100:02d}{mo:02d}{num:02d}'
        tn=len(THEMES[k])
        def tid(t):
            i=int(t); assert 1<=i<=tn,(k,no,t); return f'{sname}-{i:02d}'
        e=[]
        if r['bh'] not in BEH: e.append('bh')
        for x in r['rs']:
            if x not in REASON: e.append('rs:'+x)
        for x in r['st']:
            if x not in SIDS: e.append('st:'+x)
        if r['ch'] is not None:
            if len(r['ch'])!=5 or r['ans'] not in '12345': e.append('choice/ans')
        if e: errors.append(f'{k} {no} {e}')
        nr=list(r.get('nr',[]))
        rec={
         'id':f'{pre}-{code}','subject':sname,
         'source':{'code':code,'year':ay,'exam':EXAM[mo],'number':num,'points':4,'label':f'{y}년 {mo}월 고3 {num}번'},
         'question':r['q'],'condition':r['cond'],
         'choices':r['ch'],'answer':r['ans'],
         'answer_value':(r['ch'][int(r['ans'])-1] if r['ch'] else r['ans']),
         'figure':({'description':r['fig'],'source_page':sk[no].get('q_page')} if r['fig'] else None),
         'theme':{'primary':tid(r['th']),'primary_name':THEMES[k][int(r['th'])-1],'links':[tid(t) for t in r['lk']]},
         'first_judgment':r['fj'],'behavior':r['bh'],'reasoning':r['rs'],'strategy_ids':r['st'],
         'solution_ref':r['sol'],
         'legacy':{'category':sk[no]['legacy_category'],'book_no':no,'question_page':sk[no].get('q_page'),'solution_page':sk[no].get('sol_page')},
         'check':{'answer_match':None,'excluded':False,'needs_review':nr}}
        out.append(rec)
    ids=[x['id'] for x in out]
    if len(set(ids))!=len(ids): errors.append(f'{k} dup ids')
    json.dump(out,open(f'{OUT}/{k}.json','w'),ensure_ascii=False,indent=1)
    allrec+=out
    print(k,len(out),'/',len(sk))
json.dump(allrec,open(f'{OUT}/all.json','w'),ensure_ascii=False,indent=1)
print('\n'.join(errors[:20]), len(errors),'errors')
