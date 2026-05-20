import asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from backend.analyzer.analyze import analyze_repo
from backend.render import to_architecture_md

load_dotenv()

mcp = FastMCP(
    "RepoSensei",
    instructions=(
        "You have access to RepoSensei, an AI-powered codebase mentor. "
        "Use the analyze_repository tool to get a full architecture breakdown "
        "of any public GitHub repository, including overview, tech stack, "
        "module map, critical flows, onboarding path and suggested improvements."
    ),
)


@mcp.tool()
async def analyze_repository(repo_url: str, format: str = "markdown") -> str:
    """
    Analyze a public GitHub repository and return a full architecture breakdown.

    Args:
        repo_url: Public GitHub repository URL (e.g. https://github.com/user/repo)
        format: Output format: 'markdown' for a readable architecture doc (default),
                'json' for a structured machine-readable report
    """
    if format == "markdown":
        report, signals = await asyncio.to_thread(analyze_repo, repo_url, None, True)
        return to_architecture_md(report, signals=signals)
    else:
        report = await asyncio.to_thread(analyze_repo, repo_url)
        return report.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run()
