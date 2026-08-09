from __future__ import annotations

import json

from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

from fastdatagov.auth.service import require_role
from fastdatagov.repository import repository
from fastdatagov.web import pages

routes = APIRouter()


@routes("/app", methods=["GET"])
def dashboard(auth):
    return pages.dashboard_page(auth, repository())


@routes("/app/catalog", methods=["GET"])
def catalog(auth, q: str = "", platform: str = "", domain: str = "", trust: str = "", owner: str = "", sensitivity: str = "", refreshed: str = "", page:int=1):
    return pages.catalog_page(auth, repository(), q, platform, domain, trust, owner, sensitivity, refreshed,page)


@routes("/app/assets/{asset_id:int}", methods=["GET"])
def asset_detail(asset_id: int, auth):
    asset = repository().get_asset(asset_id, auth)
    if not asset:
        raise HTTPException(404, "Asset not found or not visible")
    return pages.asset_detail_page(auth, repository(), asset)


@routes("/app/assets/{asset_id:int}/edit", methods=["GET"])
def asset_edit(asset_id: int, auth):
    require_role(auth, "steward", "owner")
    asset = repository().get_asset(asset_id, auth)
    if not asset: raise HTTPException(404, "Asset not found or not visible")
    return pages.asset_edit_page(auth, repository(), asset)


@routes("/app/assets/{asset_id:int}/metadata", methods=["POST"])
async def asset_metadata(asset_id: int, auth, req: Request):
    require_role(auth, "steward", "owner")
    form = await req.form()
    tags=[part.strip() for part in str(form.get("tags", "")).split(",") if part.strip()]
    repository().update_asset_metadata(asset_id, auth, str(form.get("business_description", "")), str(form.get("owner", "")), str(form.get("steward", "")), str(form.get("sensitivity", "internal")), str(form.get("access_guidance", "")), tags, [int(value) for value in form.getlist("term_ids")])
    native_name=str(form.get("native_tag_name","")).strip(); native_value=str(form.get("native_tag_value","")).strip()
    if native_name and native_value: repository().queue_tag_writeback(auth,asset_id,{native_name:native_value})
    return RedirectResponse(f"/app/assets/{asset_id}", status_code=303)


@routes("/app/assets/{asset_id:int}/certify", methods=["POST"])
def asset_certify(asset_id: int, auth, status: str = "verified", expires_days: int = 365, notes: str = ""):
    require_role(auth, "owner", "governance_lead")
    repository().certify_asset(asset_id, auth, status, expires_days, notes)
    return RedirectResponse(f"/app/assets/{asset_id}", status_code=303)


@routes("/app/assets/{asset_id:int}/fields",methods=["POST"])
def asset_field_metadata(asset_id:int,auth,field_name:str,business_description:str="",classification:str=""):
    require_role(auth,"steward")
    repository().update_field_metadata(asset_id,field_name,auth,business_description,classification)
    return RedirectResponse(f"/app/assets/{asset_id}",status_code=303)


@routes("/app/products", methods=["GET"])
def products(auth): return pages.products_page(auth, repository())


@routes("/app/products/new", methods=["GET"])
def product_new(auth):
    require_role(auth, "steward", "owner")
    return pages.product_form_page(auth, repository())


@routes("/app/products/{product_id:int}/edit", methods=["GET"])
def product_edit(product_id: int, auth):
    require_role(auth, "steward", "owner")
    product = next((p for p in repository().products(auth) if p.id == product_id), None)
    if not product: raise HTTPException(404, "Data product not found or not visible")
    return pages.product_form_page(auth, repository(), product)


async def _save_product(req: Request, auth, product_id: int | None = None):
    require_role(auth, "steward", "owner")
    form=await req.form()
    repository().save_product(auth, str(form.get("name","")), str(form.get("description","")), str(form.get("domain","")), str(form.get("owner","")), str(form.get("steward","")), str(form.get("status","draft")), str(form.get("service_level","")), str(form.get("access_guidance","")), [int(v) for v in form.getlist("asset_ids")], product_id)
    return RedirectResponse("/app/products", status_code=303)


@routes("/app/products/save", methods=["POST"])
async def product_save(auth, req: Request): return await _save_product(req, auth)


@routes("/app/products/{product_id:int}/save", methods=["POST"])
async def product_update(product_id: int, auth, req: Request): return await _save_product(req, auth, product_id)


@routes("/app/products/{product_id:int}/certify",methods=["POST"])
def product_certify(product_id:int,auth,status:str="verified",expires_days:int=365,notes:str=""):
    require_role(auth,"owner","governance_lead")
    repository().certify_product(product_id,auth,status,expires_days,notes)
    return RedirectResponse("/app/products",status_code=303)


@routes("/app/lineage", methods=["GET"])
def lineage(auth, asset_id: int = 0, evidence: str = "", direction: str = "both", depth: int = 1):
    if direction not in {"both","upstream","downstream"}: direction="both"
    return pages.lineage_page(auth, repository(), asset_id or None, evidence, direction, depth)


@routes("/app/lineage/manage", methods=["GET"])
def lineage_manage(auth):
    require_role(auth, "steward", "engineer")
    return pages.lineage_manage_page(auth, repository())


@routes("/app/lineage/create", methods=["POST"])
def lineage_create(auth, source_id: int, target_id: int, operation: str = "transforms", confidence: float = .75):
    require_role(auth, "steward", "engineer")
    repository().save_lineage(auth, source_id, target_id, operation, confidence)
    return RedirectResponse("/app/lineage/manage", status_code=303)


@routes("/app/lineage/{edge_id:int}/delete", methods=["POST"])
def lineage_delete(edge_id: int, auth):
    require_role(auth, "steward", "engineer")
    repository().delete_lineage(edge_id, auth)
    return RedirectResponse("/app/lineage/manage", status_code=303)


@routes("/app/quality", methods=["GET"])
def quality(auth, status: str = ""):
    return pages.quality_page(auth, repository(), status)


@routes("/app/quality/new", methods=["GET"])
def quality_new(auth):
    require_role(auth, "steward", "engineer")
    return pages.quality_form_page(auth, repository())


@routes("/app/quality/{rule_id:int}/edit", methods=["GET"])
def quality_edit(rule_id: int, auth):
    require_role(auth, "steward", "engineer")
    rule=next((r for r in repository().quality_rules(auth) if r.id==rule_id),None)
    if not rule: raise HTTPException(404,"Quality rule not found or not visible")
    return pages.quality_form_page(auth,repository(),rule)


def _save_quality(auth, asset_id: int, name: str, rule_type: str, expression: str, threshold: float, severity: str, schedule: str, rule_id: int | None=None):
    require_role(auth,"steward","engineer")
    repository().save_quality_rule(auth,asset_id,name,rule_type,expression,threshold,severity,schedule,rule_id)
    return RedirectResponse("/app/quality",status_code=303)


@routes("/app/quality/save",methods=["POST"])
def quality_save(auth,asset_id:int,name:str,rule_type:str,expression:str,threshold:float=95,severity:str="medium",schedule:str="daily"):
    return _save_quality(auth,asset_id,name,rule_type,expression,threshold,severity,schedule)


@routes("/app/quality/{rule_id:int}/save",methods=["POST"])
def quality_update(rule_id:int,auth,asset_id:int,name:str,rule_type:str,expression:str,threshold:float=95,severity:str="medium",schedule:str="daily"):
    return _save_quality(auth,asset_id,name,rule_type,expression,threshold,severity,schedule,rule_id)


@routes("/app/quality/{rule_id:int}/run",methods=["POST"])
def quality_run(rule_id:int,auth):
    require_role(auth,"steward","engineer")
    repository().queue_quality_run(rule_id,auth)
    return RedirectResponse("/app/quality",status_code=303)


@routes("/app/quality/{rule_id:int}/enabled",methods=["POST"])
def quality_enabled(rule_id:int,auth,enabled:str="false"):
    require_role(auth,"steward","engineer")
    repository().set_quality_enabled(rule_id,auth,enabled=="true")
    return RedirectResponse("/app/quality",status_code=303)


@routes("/app/work", methods=["GET"])
def work(auth, kind: str = "", status: str = ""):
    return pages.work_page(auth, repository(), kind, status)


@routes("/app/work/{item_id:int}", methods=["GET"])
def work_detail(item_id:int,auth):
    item=next((w for w in repository().work_items(identity=auth) if w.id==item_id),None)
    if not item: raise HTTPException(404,"Work item not found or not visible")
    return pages.work_detail_page(auth,repository(),item)


@routes("/app/work/{item_id:int}/comments",methods=["POST"])
def work_comment(item_id:int,auth,body:str=""):
    repository().add_work_comment(item_id,auth,body)
    return RedirectResponse(f"/app/work/{item_id}",status_code=303)


@routes("/app/work/{item_id:int}/status", methods=["POST"])
def work_status(item_id: int, auth, req: Request, status: str = ""):
    require_role(auth, "steward", "owner", "engineer")
    item = repository().update_work_item(item_id, status, auth)
    if not item:
        raise HTTPException(404, "Work item not found")
    if req.headers.get("HX-Request"):
        return pages.work_item_partial(item, repository())
    return RedirectResponse(f"/app/work?kind={item.kind}", status_code=303)


@routes("/app/work/create", methods=["POST"])
def create_work(auth, kind: str = "", asset_id: int = 0):
    item = repository().create_work_item(kind, asset_id, auth)
    return RedirectResponse(f"/app/work?kind={item.kind}", status_code=303)


@routes("/app/glossary", methods=["GET"])
def glossary(auth, q: str = ""):
    return pages.glossary_page(auth, repository(), q)


@routes("/app/glossary/new", methods=["GET"])
def glossary_new(auth):
    require_role(auth,"steward","owner")
    return pages.glossary_form_page(auth,repository())


@routes("/app/glossary/{term_id:int}/edit", methods=["GET"])
def glossary_edit(term_id:int,auth):
    require_role(auth,"steward","owner")
    term=next((t for t in repository().glossary(identity=auth) if t.id==term_id),None)
    if not term: raise HTTPException(404,"Glossary term not found")
    return pages.glossary_form_page(auth,repository(),term)


def _save_term(auth,name,definition,domain,owner,status,term_id=None):
    require_role(auth,"steward","owner")
    repository().save_term(auth,name,definition,domain,owner,status,term_id)
    return RedirectResponse("/app/glossary",status_code=303)


@routes("/app/glossary/save",methods=["POST"])
def glossary_save(auth,name:str,definition:str,domain:str,owner:str,status:str="draft"):
    return _save_term(auth,name,definition,domain,owner,status)


@routes("/app/glossary/{term_id:int}/save",methods=["POST"])
def glossary_update(term_id:int,auth,name:str,definition:str,domain:str,owner:str,status:str="draft"):
    return _save_term(auth,name,definition,domain,owner,status,term_id)


@routes("/app/admin/adapters", methods=["GET"])
def adapters(auth):
    require_role(auth, "engineer", "admin")
    return pages.adapters_page(auth, repository())


@routes("/app/admin/{section:str}", methods=["GET"])
def admin(section:str,auth):
    if section not in {"connections","domains","accountability","access","workflows","notifications","jobs","audit","pilot"}: raise HTTPException(404,"Administration section not found")
    if section in {"connections","jobs"}: require_role(auth,"engineer","admin")
    else: require_role(auth,"governance_lead","admin")
    return pages.admin_page(auth,repository(),section)


@routes("/app/admin/domains/save",methods=["POST"])
def admin_domain_save(auth,name:str,description:str="",parent_id:int=0,domain_id:int=0):
    require_role(auth,"admin","governance_lead")
    repository().save_domain(auth,name,description,parent_id or None,domain_id or None)
    return RedirectResponse("/app/admin/domains",status_code=303)


@routes("/app/admin/accountability/save",methods=["POST"])
def admin_accountability_save(auth,scope_type:str,scope_id:int,responsibility:str,email:str,expires_days:int=365):
    require_role(auth,"owner","governance_lead","admin")
    repository().assign_accountability(auth,scope_type,scope_id,responsibility,email,expires_days)
    return RedirectResponse("/app/admin/accountability",status_code=303)


@routes("/app/admin/roles/save",methods=["POST"])
def admin_role_save(auth,principal_type:str,principal_key:str,role:str,scope_type:str="global",scope_key:str=""):
    require_role(auth,"admin")
    repository().save_role(auth,principal_type,principal_key,role,scope_type,scope_key)
    return RedirectResponse("/app/admin/access",status_code=303)


@routes("/app/admin/aliases/save",methods=["POST"])
def admin_alias_save(auth,identity_principal_type:str,identity_key:str,platform_key:str,source_principal_key:str):
    require_role(auth,"admin","governance_lead")
    repository().save_principal_alias(auth,identity_principal_type,identity_key,platform_key,source_principal_key)
    return RedirectResponse("/app/admin/access",status_code=303)


@routes("/app/admin/roles/{role_id:int}/delete",methods=["POST"])
def admin_role_delete(role_id:int,auth):
    require_role(auth,"admin")
    repository().delete_role(auth,role_id)
    return RedirectResponse("/app/admin/access",status_code=303)


@routes("/app/admin/aliases/{alias_id:int}/delete",methods=["POST"])
def admin_alias_delete(alias_id:int,auth):
    require_role(auth,"admin","governance_lead")
    repository().delete_principal_alias(auth,alias_id)
    return RedirectResponse("/app/admin/access",status_code=303)


@routes("/app/admin/connections/save",methods=["POST"])
def admin_connection_save(auth,key:str,name:str,adapter_type:str,credential_ref:str="",config_json:str="{}"):
    require_role(auth,"engineer","admin")
    try: config=json.loads(config_json)
    except json.JSONDecodeError as exc: raise HTTPException(400,"Connection configuration must be valid JSON") from exc
    if not isinstance(config,dict): raise HTTPException(400,"Connection configuration must be a JSON object")
    repository().save_connection(auth,key,name,adapter_type,credential_ref,config)
    return RedirectResponse("/app/admin/connections",status_code=303)


@routes("/app/admin/connections/{key:str}/job",methods=["POST"])
def admin_connection_job(key:str,auth,kind:str):
    require_role(auth,"engineer","admin")
    repository().queue_adapter_job(auth,key,kind)
    return RedirectResponse("/app/admin/jobs",status_code=303)


@routes("/app/admin/workflows/{kind:str}/save",methods=["POST"])
def admin_workflow_save(kind:str,auth,due_days:int,approval_role:str="",enabled:str=""):
    require_role(auth,"admin","governance_lead")
    repository().save_workflow_definition(auth,kind,due_days,approval_role,enabled=="true")
    return RedirectResponse("/app/admin/workflows",status_code=303)


@routes("/app/admin/notifications/save",methods=["POST"])
def admin_notification_save(auth,key:str,channel_type:str,endpoint_ref:str,events:str="",enabled:str=""):
    require_role(auth,"admin","governance_lead")
    repository().save_notification_channel(auth,key,channel_type,endpoint_ref,[v.strip() for v in events.split(",") if v.strip()],enabled=="true")
    return RedirectResponse("/app/admin/notifications",status_code=303)
