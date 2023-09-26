# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import uvicorn

if __name__ == '__main__':
    uvicorn.run("controller:app", port=8011)
