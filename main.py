import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, Column, String, Text, Integer, BigInteger, DateTime, Boolean, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "postfix")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "postfix")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Domain(Base):
    __tablename__ = "domain"

    domain = Column(String(255), primary_key=True)
    description = Column(String(255), nullable=False, default="")
    aliases = Column(Integer, nullable=False, default=0)
    mailboxes = Column(Integer, nullable=False, default=0)
    maxquota = Column(BigInteger, nullable=False, default=0)
    quota = Column(BigInteger, nullable=False, default=0)
    transport = Column(String(255), nullable=False, default="virtual")
    backupmx = Column(Boolean, nullable=False, default=False)
    created = Column(DateTime, nullable=False, default=datetime(2000, 1, 1))
    modified = Column(DateTime, nullable=False, default=datetime(2000, 1, 1))
    active = Column(Boolean, nullable=False, default=True)
    password_expiry = Column(Integer, nullable=False, default=0)


class Alias(Base):
    __tablename__ = "alias"

    address = Column(String(255), primary_key=True)
    goto = Column(Text, nullable=False)
    domain = Column(String(255), nullable=False, index=True)
    created = Column(DateTime, nullable=False, default=datetime(2000, 1, 1))
    modified = Column(DateTime, nullable=False, default=datetime(2000, 1, 1))
    active = Column(Boolean, nullable=False, default=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Public paths
        if path.startswith("/login") or path == "/favicon.ico":
            return await call_next(request)
        # Everything else requires a session
        if not request.session.get("user"):
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

app = FastAPI(title="MIE Postfix", docs_url=None, redoc_url=None)
# Add auth first, then session so session runs outermost and populates request.session
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=False, same_site="lax")
templates = Jinja2Templates(directory="templates")

PAGE_SIZE = 25


def paginate(query, page: int):
    total = query.count()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    items = query.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return items, page, pages, total


def get_current_user(request: Request) -> Optional[str]:
    return request.session.get("user")


def require_login(request: Request):
    # Middleware already enforces this; just return the user
    return get_current_user(request) or "admin"


# ----- Auth routes -----
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: Optional[str] = None):
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if password == ADMIN_PASSWORD:
        request.session["user"] = username.strip() or "admin"
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401,
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    domain_results = []
    alias_results = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        domain_results = (
            db.query(Domain)
            .filter(Domain.domain.ilike(term) | Domain.description.ilike(term))
            .order_by(Domain.domain)
            .limit(50)
            .all()
        )
        alias_results = (
            db.query(Alias)
            .filter(Alias.address.ilike(term) | Alias.goto.ilike(term) | Alias.domain.ilike(term))
            .order_by(Alias.address)
            .limit(50)
            .all()
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "q": q or "",
            "domain_results": domain_results,
            "alias_results": alias_results,
        },
    )


@app.get("/domains", response_class=HTMLResponse)
def domains_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    query = db.query(Domain).order_by(Domain.domain)
    items, page, pages, total = paginate(query, page)
    return templates.TemplateResponse(
        "domains.html",
        {"request": request, "user": user, "domains": items, "page": page, "pages": pages, "total": total},
    )


@app.get("/aliases", response_class=HTMLResponse)
def aliases_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    query = db.query(Alias).order_by(Alias.address)
    items, page, pages, total = paginate(query, page)
    return templates.TemplateResponse(
        "aliases.html",
        {"request": request, "user": user, "aliases": items, "page": page, "pages": pages, "total": total},
    )


# ----- Domains -----
@app.get("/domain/new", response_class=HTMLResponse)
def domain_new(request: Request, user: str = Depends(require_login)):
    return templates.TemplateResponse("domain_form.html", {"request": request, "domain": None, "user": user})


@app.post("/domain/new")
def domain_create(
    domain: str = Form(...),
    description: str = Form(""),
    aliases: int = Form(0),
    mailboxes: int = Form(0),
    maxquota: int = Form(0),
    quota: int = Form(0),
    transport: str = Form("virtual"),
    backupmx: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    now = datetime.utcnow()
    obj = Domain(
        domain=domain.strip().lower(),
        description=description,
        aliases=aliases,
        mailboxes=mailboxes,
        maxquota=maxquota,
        quota=quota,
        transport=transport or "virtual",
        backupmx=backupmx == "on",
        created=now,
        modified=now,
        active=active == "on",
    )
    db.add(obj)
    db.commit()
    return RedirectResponse("/domains", status_code=303)


@app.get("/domain/{domain}/edit", response_class=HTMLResponse)
def domain_edit(domain: str, request: Request, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Domain).filter(Domain.domain == domain).first()
    if not obj:
        raise HTTPException(404)
    return templates.TemplateResponse("domain_form.html", {"request": request, "domain": obj, "user": user})


@app.post("/domain/{domain}/edit")
def domain_update(
    domain: str,
    description: str = Form(""),
    aliases: int = Form(0),
    mailboxes: int = Form(0),
    maxquota: int = Form(0),
    quota: int = Form(0),
    transport: str = Form("virtual"),
    backupmx: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    obj = db.query(Domain).filter(Domain.domain == domain).first()
    if not obj:
        raise HTTPException(404)
    obj.description = description
    obj.aliases = aliases
    obj.mailboxes = mailboxes
    obj.maxquota = maxquota
    obj.quota = quota
    obj.transport = transport or "virtual"
    obj.backupmx = backupmx == "on"
    obj.active = active == "on"
    obj.modified = datetime.utcnow()
    db.commit()
    return RedirectResponse("/domains", status_code=303)


@app.post("/domain/{domain}/delete")
def domain_delete(domain: str, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Domain).filter(Domain.domain == domain).first()
    if obj:
        # Also delete related aliases
        db.query(Alias).filter(Alias.domain == domain).delete()
        db.delete(obj)
        db.commit()
    return RedirectResponse("/domains", status_code=303)


@app.post("/domain/{domain}/toggle")
def domain_toggle(domain: str, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Domain).filter(Domain.domain == domain).first()
    if obj:
        obj.active = not obj.active
        obj.modified = datetime.utcnow()
        db.commit()
    return RedirectResponse("/domains", status_code=303)


# ----- Aliases -----
@app.get("/alias/new", response_class=HTMLResponse)
def alias_new(request: Request, db: Session = Depends(get_db), user: str = Depends(require_login)):
    domains = db.query(Domain).order_by(Domain.domain).all()
    return templates.TemplateResponse(
        "alias_form.html", {"request": request, "alias": None, "domains": domains, "user": user}
    )


@app.post("/alias/new")
def alias_create(
    address: str = Form(...),
    goto: str = Form(...),
    domain: str = Form(...),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    now = datetime.utcnow()
    obj = Alias(
        address=address.strip().lower(),
        goto=goto.strip(),
        domain=domain.strip().lower(),
        created=now,
        modified=now,
        active=active == "on",
    )
    db.add(obj)
    db.commit()
    return RedirectResponse("/aliases", status_code=303)


@app.get("/alias/{address}/edit", response_class=HTMLResponse)
def alias_edit(address: str, request: Request, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Alias).filter(Alias.address == address).first()
    if not obj:
        raise HTTPException(404)
    domains = db.query(Domain).order_by(Domain.domain).all()
    return templates.TemplateResponse(
        "alias_form.html", {"request": request, "alias": obj, "domains": domains, "user": user}
    )


@app.post("/alias/{address}/edit")
def alias_update(
    address: str,
    goto: str = Form(...),
    domain: str = Form(...),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: str = Depends(require_login),
):
    obj = db.query(Alias).filter(Alias.address == address).first()
    if not obj:
        raise HTTPException(404)
    obj.goto = goto.strip()
    obj.domain = domain.strip().lower()
    obj.active = active == "on"
    obj.modified = datetime.utcnow()
    db.commit()
    return RedirectResponse("/aliases", status_code=303)


@app.post("/alias/{address}/delete")
def alias_delete(address: str, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Alias).filter(Alias.address == address).first()
    if obj:
        db.delete(obj)
        db.commit()
    return RedirectResponse("/aliases", status_code=303)


@app.post("/alias/{address}/toggle")
def alias_toggle(address: str, db: Session = Depends(get_db), user: str = Depends(require_login)):
    obj = db.query(Alias).filter(Alias.address == address).first()
    if obj:
        obj.active = not obj.active
        obj.modified = datetime.utcnow()
        db.commit()
    return RedirectResponse("/aliases", status_code=303)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    ssl_certfile = os.getenv("SSL_CERTFILE") or None
    ssl_keyfile = os.getenv("SSL_KEYFILE") or None
    ssl_ca_certs = os.getenv("SSL_CA_CERTS") or None

    kwargs = {"host": host, "port": port, "reload": True}
    if ssl_certfile and ssl_keyfile:
        kwargs["ssl_certfile"] = ssl_certfile
        kwargs["ssl_keyfile"] = ssl_keyfile
        if ssl_ca_certs:
            kwargs["ssl_ca_certs"] = ssl_ca_certs
        print(f"Starting HTTPS on https://{host}:{port}")
    else:
        print(f"Starting HTTP on http://{host}:{port}")

    uvicorn.run("main:app", **kwargs)

