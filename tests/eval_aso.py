"""Eval das decisões do agente nos exames médicos (ASO), com HEITOR_EXAMES=1 e o LLM de verdade.

Três comportamentos, contando só o que veio do LLM (não da rede de segurança):
  - 0505, pedreiro (ruído) com ASO inapto: pendência com prazo de 1 ou 2 dias;
  - 0502, periódico vencido E protetor vencido: UMA pendência cobrindo os dois (uma ida só do técnico);
  - 0501, tudo em dia: nenhuma pendência de exame.
Medido em 08/11: 3 de 3 rodadas nos três. Uso: python -m tests.eval_aso [rodadas]   (~25 s e ~US$ 0,01 por rodada)
"""
import os, sys, time
from collections import defaultdict
os.environ["HEITOR_EXAMES"]="1"; os.environ["HEITOR_LLM"]="on"
from heitor.agente import grafo as g
def L(fid,nome,funcao,n,data,epi,ca):
    return {"funcionario_id":fid,"nome":nome,"funcao":funcao,"linha":n,"data":data,"epi":epi,"qtd":1,"ca":ca,"motivo":"T","assinatura":True,"origem":"epi.csv"}
linhas=[L("0505","Pedro Lima","pedreiro",1,"2026-10-01","protetor auditivo","17664"),
        L("0502","Marcos Vinícius Alves","servente",1,"2025-12-01","protetor auditivo","17664"),
        L("0501","Carlos Henrique Dias","pedreiro",1,"2026-10-01","protetor auditivo","17664")]
for rodada in range(int(sys.argv[1]) if len(sys.argv)>1 else 1):
    ev=defaultdict(list); t=time.time()
    r=g.rodar_auditoria(f"au-aso-ag-{rodada}",[dict(l) for l in linhas],lambda e: ev[e.funcionario_id].append(e))
    def do_llm(fid):
        out=[]
        for i,e in enumerate(ev[fid]):
            if e.tipo=="ferramenta" and e.ferramenta=="criar_pendencia":
                d=ev[fid][i-1] if i and ev[fid][i-1].tipo=="decisao" else None
                guarda=str((d.saida or {}).get("pensamento","")).startswith("guarda-corpo") if d else True
                out.append((not guarda, e.entrada, e.saida))
        return out
    ach={a["id"]:a for a in r["achados"]}
    # 0505: inapto com prazo curto decidido pelo LLM
    inapto=[a for a in r["achados"] if a["funcionario_id"]=="0505" and a["regra"]=="aso_inapto_em_atividade"]
    p0505=[(llm,ent) for llm,ent,s in do_llm("0505") if inapto and ent.get("achado_id")==inapto[0]["id"] or (inapto and inapto[0]["id"] in (ent.get("tambem") or []))]
    c1=any(llm and str(ent.get("prazo_dias")) in ("1","2") for llm,ent in p0505)
    # 0502: uma pendência cobrindo exame + EPI, criada pelo LLM
    juntou=[ (llm,ent,s) for llm,ent,s in do_llm("0502") if ent.get("tambem")]
    c2=any(llm and isinstance(s,dict) and s.get("tambem_cobre") for llm,ent,s in juntou)
    regras_0502={ach[x]["regra"] for llm,ent,s in juntou for x in [ent.get("achado_id")]+list(s.get("tambem_cobre",[])) if x in ach}
    # 0501: nenhuma pendência de exame
    c3=not any(p for p in r["pendencias"] if p["funcionario_id"]=="0501" and ach.get(p["achado_id"],{}).get("regra","").startswith("aso_"))
    acao2=[s.get("acao") for llm,ent,s in juntou][:1]
    print(f"rodada {rodada+1} ({time.time()-t:.0f}s, modo {r['modo']}): inapto prazo curto pelo LLM {c1} {[ent.get('prazo_dias') for _,ent in p0505]} | juntou exame+EPI pelo LLM {c2} {sorted(regras_0502)} | 0501 sem pendência de exame {c3}")
    print("   ação conjunta:", acao2)
