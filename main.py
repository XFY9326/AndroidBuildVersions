import asyncio
import os
import shutil
import json
import dataclasses
import http
from typing import Optional

import aiohttp

from android_info.consts import ANDROID_MAIN_REFS
from android_info.versions import AndroidBuildNumbers
from android_info.permissions import AndroidPermissions


async def dump_permissions(client: aiohttp.ClientSession, output_dir: str, refs_api: Optional[tuple[str, int]] = None):
    android_permissions = AndroidPermissions(client, refs_api[0] if refs_api is not None else ANDROID_MAIN_REFS)

    permission_groups = await android_permissions.list_permission_groups()
    permissions = await android_permissions.list_permissions()

    with open(os.path.join(output_dir, f"permissions-{refs_api[1] if refs_api is not None else 'REL'}.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "permission_groups": {i.name: dataclasses.asdict(i) for i in permission_groups},
                "permissions": {i.name: dataclasses.asdict(i) for i in permissions},
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    del android_permissions


async def main():
    async with aiohttp.ClientSession() as client:
        android_builds = AndroidBuildNumbers(client)

        output_dir = "outputs"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        api_levels = await android_builds.list_api_levels()
        with open(os.path.join(output_dir, "api_levels.json"), "w", encoding="utf-8") as f:
            json.dump({i.api: dataclasses.asdict(i) for i in api_levels}, f, ensure_ascii=False, indent=4)

        build_versions = await android_builds.list_build_versions()
        with open(os.path.join(output_dir, "build_versions.json"), "w", encoding="utf-8") as f:
            json.dump({i.tag: dataclasses.asdict(i) for i in build_versions}, f, ensure_ascii=False, indent=4)

        permissions_output_dir = os.path.join(output_dir, "permissions")
        if not os.path.exists(permissions_output_dir):
            os.makedirs(permissions_output_dir)

        # Dump REL version
        await dump_permissions(client, permissions_output_dir)

        # Dump all API levels vesion
        for api_level in api_levels:
            for version in reversed(api_level.versions):
                latest_build_version = await android_builds.get_latest_build_version(version)
                if latest_build_version is not None:
                    try:
                        await dump_permissions(client, permissions_output_dir, (latest_build_version.tag, api_level.api))
                        break
                    except aiohttp.ClientResponseError as e:
                        if e.status != http.HTTPStatus.NOT_FOUND.value:
                            raise


if __name__ == "__main__":
    looper = asyncio.get_event_loop()
    try:
        looper.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        if not looper.is_closed:
            looper.close()
