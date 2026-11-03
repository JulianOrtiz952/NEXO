# NEXO | Restaurant Management

Personal project in development. NEXO brings restaurant administration into one application, with separate areas for platform administration and restaurant operations.

## Implemented scope

- Sign-in, sign-out and session identity through API authentication.
- Restaurant and user administration with memberships and ownership rules.
- Zone and table management, including capacity and name validation.
- Audit history and a menu API.

The code is organized into a React/Vite frontend and a Python/Django REST Framework backend. Local development uses SQLite. The API routes are in [backend/api/urls.py](backend/api/urls.py) and its tests cover identity, ownership, audit history, zones and tables. Inventory and payment workflows remain planned scope.

## Run locally

Use Python 3.12+ and Node.js 22.12+. Run the following from the repository root in PowerShell.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver
```

In a second terminal run `npm ci --prefix frontend` and `npm run dev --prefix frontend`. Open the URL printed by Vite.

## Checks

Run `backend/.venv/Scripts/python.exe backend/manage.py test api`, `npm run lint --prefix frontend` and `npm run build --prefix frontend`.

See the [domain rules](DOMAIN_RULES.md) and [data model](DATA_MODEL.md) for design context.

