from __future__ import annotations

from dataclasses import asdict

import csv
import io

from fasthtml.common import APIRouter, HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fastdatagov.auth.service import require_role
from fastdatagov.repository import repository

routes = APIRouter()


def envelope(data, *, count: int | None = None):
    payload = {"data": data, "meta": {"api_version": "v1"}}
    if count is not None:
        payload["meta"]["count"] = count
    return JSONResponse(payload)


def csv_safe(value):
    text=str(value)
    return "'"+text if text.startswith(("=","+","-","@","\t","\r")) else text


@routes("/api/v1",methods=["GET"])
def api_index(auth):
    return envelope({"name":"FastDataGov API","version":"v1","documentation":"repository:docs/API.md","resources":["assets","lineage","quality","glossary","products","work","domains","adapters","audit","jobs","pilot-metrics","exports","integrations"]})


@routes("/api/v1/assets", methods=["GET"])
def assets(auth, q: str = "", platform: str = "", domain: str = "", trust: str = "", owner: str = "", sensitivity: str = "", refreshed: str = "", page:int=1, page_size:int=100):
    page=max(page,1); page_size=min(max(page_size,1),500)
    rows = repository().list_assets(q, platform, domain, trust, auth, owner, sensitivity, refreshed,page_size,(page-1)*page_size)
    payload_data={"data":[asdict(asset) for asset in rows],"meta":{"api_version":"v1","count":len(rows),"page":page,"page_size":page_size}}
    return JSONResponse(payload_data)


@routes("/api/v1/assets/{asset_id:int}", methods=["GET"])
def asset(asset_id: int, auth):
    row = repository().get_asset(asset_id, auth)
    if not row:
        raise HTTPException(404, "Asset not found or not visible")
    return envelope(asdict(row))


@routes("/api/v1/lineage", methods=["GET"])
def lineage(auth, asset_id: int = 0):
    rows = repository().lineage(asset_id or None, auth)
    return envelope([asdict(edge) for edge in rows], count=len(rows))


@routes("/api/v1/lineage/impact", methods=["GET"])
def lineage_impact(auth,asset_id:int,direction:str="downstream",depth:int=3):
    if direction not in {"upstream","downstream","both"}: raise HTTPException(400,"Direction must be upstream, downstream or both")
    if not repository().get_asset(asset_id,auth): raise HTTPException(404,"Asset not found or not visible")
    all_edges=repository().lineage(identity=auth); frontier={asset_id}; reached={asset_id}; selected=[]
    for _ in range(max(1,min(depth,5))):
        level=[e for e in all_edges if (direction in {"upstream","both"} and e.target_id in frontier) or (direction in {"downstream","both"} and e.source_id in frontier)]
        selected.extend(e for e in level if e not in selected)
        frontier=({e.source_id for e in level}|{e.target_id for e in level})-reached; reached|=frontier
    return envelope({"root_asset_id":asset_id,"direction":direction,"depth":min(max(depth,1),5),"affected_asset_ids":sorted(reached-{asset_id}),"edges":[asdict(e) for e in selected]})


@routes("/api/v1/quality", methods=["GET"])
def quality(auth):
    rows = repository().quality_rules(auth)
    return envelope([asdict(rule) for rule in rows], count=len(rows))


@routes("/api/v1/glossary", methods=["GET"])
def glossary(auth, q: str = ""):
    rows = repository().glossary(q, auth)
    return envelope([asdict(term) for term in rows], count=len(rows))


@routes("/api/v1/adapters", methods=["GET"])
def adapters(auth):
    rows = repository().adapters(auth)
    return envelope([asdict(adapter) for adapter in rows], count=len(rows))


@routes("/api/v1/products", methods=["GET"])
def products(auth):
    rows=repository().products(auth)
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/work", methods=["GET"])
def work(auth,kind:str="",status:str=""):
    rows=repository().work_items(kind,status,auth)
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/domains", methods=["GET"])
def domains(auth):
    rows=repository().domains()
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/audit", methods=["GET"])
def audit(auth,limit:int=50):
    rows=repository().audit(min(max(limit,1),500),auth)
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/jobs", methods=["GET"])
def jobs(auth,limit:int=50):
    require_role(auth,"engineer","governance_lead","admin")
    rows=repository().jobs(min(max(limit,1),500))
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/pilot-metrics", methods=["GET"])
def pilot_metrics(auth):
    rows=repository().pilot_metrics()
    return envelope([asdict(row) for row in rows],count=len(rows))


@routes("/api/v1/exports/assets", methods=["GET"])
def export_assets(auth):
    rows=repository().list_assets(identity=auth)
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(("id","name","qualified_name","type","platform","domain","owner","steward","sensitivity","certification","quality_score","trust_score","usage_30d"))
    for row in rows:
        writer.writerow(tuple(csv_safe(value) for value in (row.id,row.name,row.qualified_name,row.asset_type,row.platform,row.domain,row.owner,row.steward,row.sensitivity,row.certification,row.quality_score,row.trust_score,row.usage_30d)))
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=fastdatagov-assets.csv"})


async def payload(request:Request)->dict:
    try: value=await request.json()
    except Exception as exc: raise HTTPException(400,"A valid JSON request body is required") from exc
    if not isinstance(value,dict): raise HTTPException(400,"JSON body must be an object")
    return value


@routes("/api/v1/glossary",methods=["POST"])
async def create_term(auth,request:Request):
    require_role(auth,"steward","owner"); body=await payload(request)
    row=repository().save_term(auth,str(body.get("name","")),str(body.get("definition","")),str(body.get("domain","")),str(body.get("owner",auth.email)),str(body.get("status","draft")),body.get("id"))
    return envelope(asdict(row))


@routes("/api/v1/lineage",methods=["POST"])
async def create_lineage(auth,request:Request):
    require_role(auth,"steward","engineer"); body=await payload(request)
    row=repository().save_lineage(auth,int(body.get("source_id",0)),int(body.get("target_id",0)),str(body.get("operation","transforms")),float(body.get("confidence",.75)))
    return envelope(asdict(row))


@routes("/api/v1/quality",methods=["POST"])
async def create_quality(auth,request:Request):
    require_role(auth,"steward","engineer"); body=await payload(request)
    row=repository().save_quality_rule(auth,int(body.get("asset_id",0)),str(body.get("name","")),str(body.get("rule_type","validity")),str(body.get("expression","")),float(body.get("threshold",95)),str(body.get("severity","medium")),str(body.get("schedule","daily")),body.get("id"))
    return envelope(asdict(row))


@routes("/api/v1/quality/{rule_id:int}/runs",methods=["POST"])
def run_quality(rule_id:int,auth):
    require_role(auth,"steward","engineer")
    return envelope({"job_id":repository().queue_quality_run(rule_id,auth),"status":"queued"})


@routes("/api/v1/work/{item_id:int}/comments",methods=["POST"])
async def comment_work(item_id:int,auth,request:Request):
    body=await payload(request); row=repository().add_work_comment(item_id,auth,str(body.get("body","")))
    return envelope(asdict(row))


@routes("/api/v1/integrations/lineage",methods=["POST"])
async def import_lineage(auth,request:Request):
    require_role(auth,"engineer"); body=await payload(request)
    evidence=str(body.get("evidence_type","inferred"))
    if evidence not in {"inferred","native","query_history"}: raise HTTPException(400,"Integration evidence must be inferred, native or query_history")
    visible=repository().list_assets(identity=auth); by_name={a.qualified_name.lower():a for a in visible}; created=[]; missing=[]
    for item in body.get("edges",[]):
        source=by_name.get(str(item.get("source","")).lower()); target=by_name.get(str(item.get("target","")).lower())
        if not source or not target:
            missing.append({"source":item.get("source"),"target":item.get("target")}); continue
        edge=repository().save_lineage(auth,source.id,target.id,str(item.get("operation","transforms")),float(item.get("confidence",.9)),evidence); created.append(asdict(edge))
    return envelope({"created":created,"unmatched":missing})


@routes("/api/v1/integrations/dbt",methods=["POST"])
async def import_dbt(auth,request:Request):
    require_role(auth,"engineer"); manifest=await payload(request)
    resources={**dict(manifest.get("sources",{})),**dict(manifest.get("nodes",{}))}; visible=repository().list_assets(identity=auth); by_name={a.qualified_name.lower():a for a in visible}; created=[]; unmatched=set()
    def qualified(node): return ".".join(str(v) for v in (node.get("database"),node.get("schema"),node.get("alias") or node.get("name")) if v).lower()
    for unique_id,node in dict(manifest.get("nodes",{})).items():
        target=by_name.get(qualified(node))
        if not target: unmatched.add(unique_id); continue
        for dependency in node.get("depends_on",{}).get("nodes",[]):
            source_node=resources.get(dependency,{}); source=by_name.get(qualified(source_node))
            if not source: unmatched.add(dependency); continue
            created.append(asdict(repository().save_lineage(auth,source.id,target.id,"dbt model dependency",1.0,"native")))
    return envelope({"created":created,"unmatched_resource_ids":sorted(unmatched)})
