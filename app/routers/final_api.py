from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_token, get_user_from_request, hash_password, verify_password
from app.database import get_db
from app.models import Alamat, FormField, Layanan, LayananVarian, Pesanan, User

router = APIRouter(prefix="/api/final", tags=["final"])


def _norm(v: str | None) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).casefold()


def _phone(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _current(request: Request) -> dict:
    user = get_user_from_request(request)
    if not user or not user.get("id"):
        raise HTTPException(401, "Silakan login terlebih dahulu")
    return user


@router.post("/login")
async def login(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    identity = str(data.get("identity") or "").strip()
    password = str(data.get("password") or "")
    if not identity or not password:
        return JSONResponse({"error":"Nomor HP/email dan password wajib diisi"}, status_code=400)
    phone = _phone(identity)
    stmt = select(User).where(or_(User.email == identity.lower(), User.no_hp == identity, User.no_hp == phone))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password):
        return JSONResponse({"error":"Nomor HP/email atau password salah"}, status_code=401)
    token = create_token({"id":user.id,"email":user.email,"nama":user.nama,"role":user.role})
    redirect = "/admin/dashboard" if user.role == "ADMIN" else "/beranda"
    resp = JSONResponse({"redirect":redirect})
    resp.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=86400)
    return resp


@router.post("/register")
async def register(data: dict, db: AsyncSession = Depends(get_db)):
    nama = str(data.get("nama") or "").strip()
    identity = str(data.get("identity") or "").strip()
    password = str(data.get("password") or "")
    if not nama or not identity or len(password) < 6:
        return JSONResponse({"error":"Data pendaftaran belum lengkap"}, status_code=400)
    is_email = "@" in identity
    if is_email:
        email, no_hp = identity.lower(), ""
        exists = await db.execute(select(User).where(User.email == email))
    else:
        no_hp = _phone(identity)
        if len(no_hp) < 8:
            return JSONResponse({"error":"Nomor HP tidak valid"}, status_code=400)
        email = f"{no_hp}@phone.bantudulu.local"
        exists = await db.execute(select(User).where(or_(User.no_hp == no_hp, User.email == email)))
    if exists.scalar_one_or_none():
        return JSONResponse({"error":"Akun sudah terdaftar"}, status_code=400)
    user = User(nama=nama,email=email,no_hp=no_hp,password=hash_password(password),role="CUSTOMER")
    db.add(user); await db.commit(); await db.refresh(user)
    token = create_token({"id":user.id,"email":user.email,"nama":user.nama,"role":user.role})
    resp = JSONResponse({"redirect":"/beranda"});resp.set_cookie("token",token,httponly=True,secure=True,samesite="lax",max_age=86400);return resp


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    auth = _current(request); user = await db.get(User, auth["id"])
    addr_res = await db.execute(select(Alamat).where(Alamat.user_id == user.id).order_by(Alamat.is_default.desc()))
    addr = addr_res.scalars().first()
    email = "" if user.email.endswith("@phone.bantudulu.local") else user.email
    return {"id":user.id,"nama":user.nama,"email":email,"no_hp":user.no_hp,"role":user.role,"address":({"id":addr.id,"label":addr.label,"alamat_lengkap":addr.alamat_lengkap} if addr else None)}


@router.get("/orders")
async def orders(request: Request, db: AsyncSession = Depends(get_db)):
    auth = _current(request)
    result = await db.execute(select(Pesanan).where(Pesanan.user_id == auth["id"]).order_by(Pesanan.created_at.desc()))
    out=[]
    for p in result.scalars().all():
        l=await db.get(Layanan,p.layanan_id);v=await db.get(LayananVarian,p.varian_id)
        payment="cod"
        try: payment=(json.loads(p.form_data or "{}") or {}).get("metode_pembayaran","cod")
        except Exception: pass
        out.append({"id":p.id,"kode":p.kode,"status":p.status,"layanan_nama":l.nama if l else "Pesanan","varian_nama":v.nama if v else "","alamat":p.alamat,"jadwal":p.jadwal,"jam":p.jam,"durasi":p.durasi,"total_harga":p.total_harga,"catatan":p.catatan or "","metode_pembayaran":payment,"created_at":p.created_at.isoformat(),"created_label":p.created_at.strftime("%d/%m/%Y")})
    return out


async def _find_service(db: AsyncSession, name: str) -> Layanan | None:
    result=await db.execute(select(Layanan).where(Layanan.aktif == True))
    for s in result.scalars().all():
        if _norm(s.nama)==_norm(name): return s
    aliases={"pijat & relaksasi":{"trapis","pijat & relaksasi"}}
    for canonical,names in aliases.items():
        if _norm(name) in {_norm(x) for x in names}:
            for s in (await db.execute(select(Layanan).where(Layanan.aktif == True))).scalars().all():
                if _norm(s.nama) in {_norm(x) for x in names}: return s
    return None


@router.post("/orders")
async def create_order(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    auth=_current(request); service_name=str(data.get("service_name") or "").strip(); variant_name=str(data.get("variant_name") or "").strip()
    service=await _find_service(db,service_name)
    if not service: raise HTTPException(404,f"Layanan tidak ditemukan: {service_name}")
    variants=(await db.execute(select(LayananVarian).where(LayananVarian.layanan_id==service.id))).scalars().all()
    variant=next((v for v in variants if _norm(v.nama)==_norm(variant_name)),None)
    price_hint=int(data.get("price_hint") or 0)
    if not variant and price_hint: variant=next((v for v in variants if int(v.harga)==price_hint),None)
    if not variant and len(variants)==1: variant=variants[0]
    if not variant: raise HTTPException(400,f"Varian layanan tidak ditemukan: {variant_name}")
    duration=max(1,int(data.get("duration") or 1));extras=data.get("extras") or {}; addon_total=0
    selected_addons=extras.get("addons") or []
    fields=(await db.execute(select(FormField).where(FormField.layanan_id==service.id))).scalars().all()
    addon_prices={_norm((a.get("label") if isinstance(a,dict) else str(a))):0 for a in selected_addons}
    for f in fields:
        label=_norm(f.label.replace("+",""));
        for key in list(addon_prices):
            if key==label or key in label or label in key: addon_prices[key]=int(f.harga_tambahan or 0)
    addon_total=sum(addon_prices.values())
    if extras.get("floor2"): addon_total += 50000
    total=int(variant.harga)*duration+addon_total
    alamat=str(data.get("address") or "").strip();jadwal=str(data.get("jadwal") or "").strip();jam=str(data.get("jam") or "").strip();catatan=str(data.get("catatan") or "").strip();payment=str(data.get("metode_pembayaran") or "cod")
    if not alamat or not jadwal: raise HTTPException(400,"Alamat dan jadwal wajib diisi")
    import uuid
    kode=f"BD-{uuid.uuid4().hex[:6].upper()}"
    form={"metode_pembayaran":payment,"extras":extras}
    order=Pesanan(user_id=auth["id"],layanan_id=service.id,varian_id=variant.id,kode=kode,status="menunggu",alamat=alamat,jadwal=jadwal,jam=jam,durasi=duration,total_harga=total,catatan=catatan,form_data=json.dumps(form,ensure_ascii=False))
    db.add(order);await db.commit();await db.refresh(order)
    return {"success":True,"data":{"id":order.id,"kode":order.kode,"status":order.status,"total_harga":order.total_harga}}


@router.put("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    auth=_current(request);result=await db.execute(select(Pesanan).where(Pesanan.id==order_id,Pesanan.user_id==auth["id"]));p=result.scalar_one_or_none()
    if not p: raise HTTPException(404,"Pesanan tidak ditemukan")
    if p.status not in {"menunggu","diproses","ditugaskan"}: raise HTTPException(400,"Pesanan pada status ini tidak dapat dibatalkan")
    p.status="dibatalkan";await db.commit();return {"success":True,"status":p.status}
