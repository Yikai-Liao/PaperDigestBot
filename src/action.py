import asyncio
import io
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta

import aiohttp
from loguru import logger


async def trigger_workflow(
    session: aiohttp.ClientSession,
    pat: str,
    owner: str,
    repo: str,
    workflow_file: str,
    branch: str,
    inputs: dict = None,
):
    """
    异步触发 GitHub Actions 工作流
    """
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": branch, "inputs": inputs or {}}

    async with session.post(url, headers=headers, json=payload) as response:
        if response.status == 204:
            logger.info(f"成功触发工作流: {workflow_file}")
            return True
        else:
            error_text = await response.text()
            logger.error(f"触发工作流失败，状态码: {response.status}，错误: {error_text}")
            return False


async def get_triggered_workflow_run(
    session: aiohttp.ClientSession,
    pat: str,
    owner: str,
    repo: str,
    workflow_file: str,
    branch: str,
    trigger_time: datetime,
    max_attempts: int = 10,
    poll_interval: int = 2,
):
    """
    获取刚触发的运行 ID，通过工作流文件名、分支和触发时间过滤
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    for attempt in range(max_attempts):
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                for run in data["workflow_runs"]:
                    if (
                        run["path"] == f".github/workflows/{workflow_file}"
                        and run["head_branch"] == branch
                        and datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                            tzinfo=UTC
                        )
                        >= trigger_time
                    ):
                        logger.info(f"找到触发的运行 ID: {run['id']}")
                        return run
                logger.info(f"尝试 {attempt + 1}/{max_attempts} 未找到匹配的运行，正在重试...")
                await asyncio.sleep(poll_interval)
            else:
                error_text = await response.text()
                logger.error(f"获取运行列表失败，状态码: {response.status}，错误: {error_text}")
                return None
        await asyncio.sleep(poll_interval)

    logger.warning("未找到匹配的工作流运行，可能是触发延迟或配置错误")
    return None


async def wait_for_workflow_completion(
    session: aiohttp.ClientSession,
    pat: str,
    owner: str,
    repo: str,
    run_id: int,
    poll_interval: int = 20,
):
    """
    等待工作流运行完成
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    while True:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                run = await response.json()
                status = run["status"]
                conclusion = run["conclusion"]
                logger.info(f"工作流状态: {status}, 结论: {conclusion}")
                if status == "completed":
                    if conclusion == "success":
                        logger.info("工作流成功完成")
                        return True
                    else:
                        logger.error(f"工作流失败，结论: {conclusion}")
                        return False
                await asyncio.sleep(poll_interval)
            else:
                error_text = await response.text()
                logger.error(f"检查工作流状态失败，状态码: {response.status}，错误: {error_text}")
                return False


async def download_artifact(
    session: aiohttp.ClientSession,
    pat: str,
    owner: str,
    repo: str,
    run_id: int,
    artifact_name: str,
    output_dir: str = None,
):
    """
    下载指定的 artifact 并直接解压到临时目录

    Args:
        session: aiohttp会话
        pat: GitHub个人访问令牌
        owner: 仓库所有者
        repo: 仓库名称
        run_id: 工作流运行ID
        artifact_name: artifact名称
        output_dir: 输出目录，如果为None则创建一个跨平台的临时目录

    Returns:
        解压目录的路径，失败则返回None
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 如果没有指定输出目录，创建一个跨平台的临时目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="paperdigest_")

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            for artifact in data["artifacts"]:
                if artifact["name"] == artifact_name:
                    download_url = artifact["archive_download_url"]
                    async with session.get(download_url, headers=headers) as download_response:
                        if download_response.status == 200:
                            # 直接读取ZIP数据到内存
                            zip_data = await download_response.read()

                            # 从内存中解压ZIP数据到输出目录
                            try:
                                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                                    zip_ref.extractall(output_dir)
                                logger.info(
                                    f"成功下载并解压 artifact: {artifact_name} 到 {output_dir}"
                                )
                                return output_dir
                            except Exception as e:
                                logger.error(f"解压artifact失败: {e}")
                                return None
                        else:
                            error_text = await download_response.text()
                            logger.error(
                                f"下载 artifact 失败，状态码: {download_response.status}，错误: {error_text}"
                            )
                            return None
            logger.warning(f"未找到 artifact: {artifact_name}")
            return None
        else:
            error_text = await response.text()
            logger.error(f"获取 artifact 列表失败，状态码: {response.status}，错误: {error_text}")
            return None


async def run_workflow(
    pat: str,
    owner: str,
    repo: str,
    workflow_file: str,
    branch: str,
    inputs: dict = None,
    artifact_name: str = "recommendations",
):
    """
    主函数，运行工作流
    """
    async with aiohttp.ClientSession() as session:
        # 1. 触发工作流并记录触发时间
        trigger_time = datetime.now(UTC) - timedelta(seconds=10)
        if not await trigger_workflow(session, pat, owner, repo, workflow_file, branch, inputs):
            return None
        # 2. 获取刚触发的运行
        run = await get_triggered_workflow_run(
            session, pat, owner, repo, workflow_file, branch, trigger_time
        )
        if not run:
            return None
        # 3. 等待工作流完成
        if not await wait_for_workflow_completion(session, pat, owner, repo, run["id"]):
            return None

        # 4. 下载artifact并直接解压到临时目录（优化IO：直接内存解压）
        temp_dir = await download_artifact(session, pat, owner, repo, run["id"], artifact_name)
        return temp_dir


if __name__ == "__main__":
    PAT = ""  # 替换为你的 Personal Access Token
    OWNER = "Yikai-Liao"  # 替换为仓库所有者（用户名或组织名）
    REPO = "PaperDigestAction"  # 替换为仓库名称
    WORKFLOW_FILE = "recommend.yml"  # 替换为工作流文件名
    BRANCH = "main"  # 替换为分支名称
    INPUTS = {}  # 可选：工作流输入参数
    ARTIFACT_NAME = "summarized"
    temp_dir = asyncio.run(
        run_workflow(PAT, OWNER, REPO, WORKFLOW_FILE, BRANCH, INPUTS, ARTIFACT_NAME)
    )
    logger.info(f"Workflow returned temp_dir: {temp_dir}")
    import polars as pl

    if temp_dir and os.path.exists(temp_dir):
        try:
            parquet_path = os.path.join(temp_dir, "summarized.parquet")
            if os.path.exists(parquet_path):
                logger.info(f"Parquet head: {pl.read_parquet(parquet_path).head()}")
            else:
                logger.error(f"Parquet file not found at {parquet_path}")
        except Exception as e:
            logger.error(f"读取parquet文件失败: {e}", exc_info=True)
    elif temp_dir:
        logger.warning(
            f"Temporary directory {temp_dir} was specified but does not exist for Parquet reading."
        )
    else:
        logger.warning("Workflow did not return a temporary directory. Cannot read Parquet.")

    # 运行完后，删除临时目录
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"成功删除临时目录: {temp_dir}")
        except OSError as e:
            logger.error(f"删除临时目录失败: {e}", exc_info=True)
    elif temp_dir:
        logger.info(f"临时目录 {temp_dir} 已被删除或不存在，无需再次操作。")
    else:
        logger.info("没有创建临时目录或目录已被删除。")
