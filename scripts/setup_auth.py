"""One-time interactive OAuth flow. Run this locally once to authorize the app;
re-run only if the stored refresh token gets revoked/expired."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth import CLIENT_SECRET_PATH, SCOPES, TOKEN_PATH  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402


def main() -> None:
    if not CLIENT_SECRET_PATH.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRET_PATH}.\n"
            "Download your OAuth Desktop-app client JSON from Google Cloud Console "
            "(APIs & Services > Credentials) and save it at that path first."
        )

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved credentials to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
