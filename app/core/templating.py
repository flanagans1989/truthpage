from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.db.models.mixins import utc_now

templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")
templates.env.globals["ga_measurement_id"] = settings.GA_MEASUREMENT_ID
# Lets a template compute "how long ago" without every router pre-computing
# it — used by public_trust.html's last-verified age coloring.
templates.env.globals["utc_now"] = utc_now
