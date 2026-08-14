from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.config import settings

templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")
templates.env.globals["ga_measurement_id"] = settings.GA_MEASUREMENT_ID
