# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import uvicorn

if __name__ == '__main__':
    uvicorn.run("controller:app", port=8002)
