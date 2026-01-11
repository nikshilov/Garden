.PHONY: ios

# Generate Xcode project & run lint
ios:
	@xcodegen generate --spec ios/project.yml --use-cache
	@echo "Running SwiftLint (non-fatal)..."
# @command -v swiftlint >/dev/null 2>&1 && swiftlint --fix --quiet || true

.PHONY: backend-install backend-run set-webhooks backend-recreate-venv

# Create virtualenv and install Python deps for backend
backend-install:
	@python3 -m venv backend/.venv || true
	@backend/.venv/bin/python -m pip install --upgrade pip
	@backend/.venv/bin/python -m pip install -r backend/requirements.txt

# Run FastAPI backend locally (reload)
backend-run:
	@cd backend && ../backend/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 5050 --reload

# Force clean and recreate venv using system python3
backend-recreate-venv:
	@rm -rf backend/.venv
	@/usr/bin/env python3 -m venv backend/.venv
	@backend/.venv/bin/python -m pip install --upgrade pip
	@backend/.venv/bin/python -m pip install -r backend/requirements.txt

# Register Telegram webhooks using env from .env and WEBHOOK_BASE_URL
set-webhooks:
	@set -a; [ -f .env ] && . .env; set +a; bash backend/scripts/set_webhooks.sh
