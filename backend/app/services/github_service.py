"""Minimal GitHub REST client for the optimization agent.

The platform's token can start the optimizer workflow and read its runs and
pull requests (Actions: read and write, Pull requests: read, on one repo). It
cannot push code. The code is written inside GitHub Actions by the Claude Code
agent and pushed by that run's own short-lived GITHUB_TOKEN, so nothing in
this app can change the repository directly.
"""

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(15.0)


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _github_time(value: str | None) -> datetime | None:
    """GitHub timestamps ('2026-10-05T14:03:11Z') as naive UTC, like the DB."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


class GitHubService:
    def __init__(self, token: str, repo: str):
        self.token = (token or "").strip()
        self.repo = (repo or "").strip().strip("/")

    @property
    def configured(self) -> bool:
        return bool(self.token and "/" in self.repo)

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self.configured:
            raise GitHubError("GitHub is not configured (OPTIMIZER_GITHUB_TOKEN)")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.request(method, f"{API}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub unreachable: {type(exc).__name__}") from exc
        if resp.status_code >= 400:
            message = ""
            try:
                message = resp.json().get("message", "")
            except ValueError:
                message = resp.text[:200]
            raise GitHubError(f"GitHub {resp.status_code}: {message}".strip(), resp.status_code)
        return resp

    async def workflow_registered(self, workflow: str) -> bool:
        """True when GitHub knows the workflow (it is on the default branch)."""
        try:
            await self._request("GET", f"/repos/{self.repo}/actions/workflows/{workflow}")
            return True
        except GitHubError as exc:
            if exc.status_code == 404:
                return False
            raise

    async def dispatch_workflow(self, workflow: str, ref: str, inputs: dict[str, str]) -> None:
        """Start a workflow_dispatch run. GitHub answers 204 with no run id;
        the run is found afterwards by its run-name (see find_run)."""
        await self._request(
            "POST",
            f"/repos/{self.repo}/actions/workflows/{workflow}/dispatches",
            json={"ref": ref, "inputs": inputs},
        )

    async def find_run(
        self, workflow: str, ref: str, title_suffix: str, created_after: datetime | None
    ) -> dict | None:
        """Newest dispatch run of ``workflow`` on ``ref`` whose display title
        ends with ``title_suffix`` (the workflow's run-name carries the
        proposal number), created after ``created_after``."""
        resp = await self._request(
            "GET",
            f"/repos/{self.repo}/actions/workflows/{workflow}/runs",
            params={"event": "workflow_dispatch", "branch": ref, "per_page": 30},
        )
        for run in resp.json().get("workflow_runs", []):
            if not str(run.get("display_title", "")).endswith(title_suffix):
                continue
            created = _github_time(run.get("created_at"))
            if created_after and created and created < created_after:
                continue
            return run
        return None

    async def find_pull_request(self, branch: str) -> dict | None:
        resp = await self._request(
            "GET",
            f"/repos/{self.repo}/pulls",
            params={"head": f"{self.owner}:{branch}", "state": "all", "per_page": 5},
        )
        pulls = resp.json()
        return pulls[0] if pulls else None
