"""
Thin wrapper around the RocketRide SDK so the rest of the app calls plain
async functions instead of juggling connect/use/send/terminate everywhere.

Requires ROCKETRIDE_URI and ROCKETRIDE_APIKEY in .env - these get written
automatically the first time you connect the VS Code extension in Local mode
(see buildathon instructions, section 5). Point them at your Cloud engine for
the demo; nothing else in this file changes.
"""
import os
from pathlib import Path
from rocketride import RocketRideClient

PIPELINES_DIR = Path(__file__).resolve().parent.parent.parent / "pipelines"


async def run_pipeline(pipe_filename: str, payload, mimetype: str = "application/json"):
    """
    Runs one .pipe file end-to-end for a single payload and returns its output.
    Always terminates the run - leaving this out leaks a live pipeline on the
    engine (see the buildathon doc's warning about orphaned runs).
    """
    uri = os.environ["ROCKETRIDE_URI"]
    apikey = os.environ["ROCKETRIDE_APIKEY"]
    filepath = str(PIPELINES_DIR / pipe_filename)

    async with RocketRideClient(uri=uri, auth=apikey) as client:
        result = await client.use(filepath=filepath)
        token = result["token"]
        try:
            return await client.send(
                token,
                payload,
                objinfo={"name": pipe_filename},
                mimetype=mimetype,
            )
        finally:
            await client.terminate(token)


async def run_pipeline_batch(pipe_filename: str, payloads: list, mimetype: str = "application/json"):
    """
    Runs one .pipe file once against a *list* of records (the batch webhook
    node handles the fan-out). Use this for the weekly report and for
    optimization cycles across every campaign, not a loop of single calls.
    """
    return await run_pipeline(pipe_filename, payloads, mimetype)
