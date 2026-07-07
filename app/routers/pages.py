"""Public marketing/legal pages (no auth): landing, pricing, terms, privacy, refunds."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
_templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _templates.TemplateResponse(request, "landing.html", {})


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return _templates.TemplateResponse(request, "pricing.html", {})


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return _templates.TemplateResponse(request, "terms.html", {})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return _templates.TemplateResponse(request, "privacy.html", {})


@router.get("/refunds", response_class=HTMLResponse)
async def refunds(request: Request):
    return _templates.TemplateResponse(request, "refunds.html", {})
