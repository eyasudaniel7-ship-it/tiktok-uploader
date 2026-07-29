import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import requests

from src.config import Account, TOKEN_REFRESH, is_mock_mode

TOKEN_FILE = Path(__file__).resolve().parents[1] / ".env"


class TikTokAuth:
    def __init__(self, account: Account):
        self.account = account
        self._token_expires_at: Optional[datetime] = None
        self._token_type: Optional[str] = None

    def get_valid_token(self) -> str:
        if is_mock_mode():
            return "mock_access_token"

        token = self.account.access_token
        if not token:
            raise RuntimeError(
                f"No access_token for {self.account.name}. "
                "Run OAuth flow first (see references/oauth_flow.md)."
            )

        if self._is_token_expired():
            token = self._refresh()

        return token

    def _is_token_expired(self) -> bool:
        if not self._token_expires_at:
            return False
        return datetime.now(timezone.utc) + timedelta(hours=1) > self._token_expires_at

    def _refresh(self) -> str:
        refresh = self.account.refresh_token
        if not refresh:
            raise RuntimeError(
                f"No refresh_token for {self.account.name}. "
                "Re-run OAuth flow (see references/oauth_flow.md)."
            )

        resp = requests.post(
            TOKEN_REFRESH,
            data={
                "client_key": self.account.client_key,
                "client_secret": self.account.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            timeout=30,
        )
        data = resp.json()

        if "access_token" not in data.get("data", {}):
            raise RuntimeError(
                f"Token refresh failed for {self.account.name}: "
                f"{data.get('error', 'unknown')}. Re-run OAuth flow."
            )

        token_data = data["data"]
        new_access = token_data["access_token"]
        new_refresh = token_data.get("refresh_token", refresh)
        expires_in = token_data.get("expires_in", 86400)

        self._update_env_file(new_access, new_refresh)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self._token_type = token_data.get("token_type", "Bearer")

        return new_access

    def _update_env_file(self, access: str, refresh: str):
        prefix = self.account.name.upper()
        if TOKEN_FILE.exists():
            lines = TOKEN_FILE.read_text(encoding="utf-8").splitlines()
        else:
            lines = []

        new_lines = []
        written_access = written_refresh = False
        for line in lines:
            if line.startswith(f"{prefix}_ACCESS_TOKEN="):
                new_lines.append(f'{prefix}_ACCESS_TOKEN={access}')
                written_access = True
            elif line.startswith(f"{prefix}_REFRESH_TOKEN="):
                new_lines.append(f'{prefix}_REFRESH_TOKEN={refresh}')
                written_refresh = True
            else:
                new_lines.append(line)

        if not written_access:
            new_lines.append(f'{prefix}_ACCESS_TOKEN={access}')
        if not written_refresh:
            new_lines.append(f'{prefix}_REFRESH_TOKEN={refresh}')

        TOKEN_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def get_auth_header(self) -> dict:
        token = self.get_valid_token()
        ttype = self._token_type or "Bearer"
        return {"Authorization": f"{ttype} {token}"}
